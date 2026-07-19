# Project Initiation & System Design Document
## LLM-Assisted Data Dictionary & Cross-Dataset Relationship Discovery

**Status:** Draft for review
**Stage:** Pre-build design

---

## 1. What We Are Building

An internal system that connects to our existing MySQL, PostgreSQL, and Redshift datasets, automatically documents every table and column into a searchable data dictionary, and discovers relationships across tables and datasets — including ones with no formally declared foreign key.

The system does three things:
1. **Extracts** schema, statistics, and safely sampled data from every connected data source
2. **Documents** each table and column in plain English using an LLM, grounded in real schema and statistics
3. **Discovers** relationships between columns across tables and datasets, validated against real data before being reported

The output is a browsable catalog: what data exists, what each field means, and how tables connect to each other.

---

## 2. Why We Are Building It

- Datasets have accumulated across multiple projects with no single source of truth for what tables exist, what columns mean, or how they relate
- New team members and cross-project work currently require asking around or reverse-engineering schemas by hand
- Undocumented relationships between tables are a recurring source of wrong joins and incorrect metrics in past reporting work
- A living, auto-refreshing dictionary reduces this to a searchable reference instead of institutional memory

---

## 3. Scope

**In scope:**
- MySQL application databases
- PostgreSQL databases
- Redshift (DWH)
- All tables within these that are used across current and past analytics projects

**Out of scope (for now):**
- BigQuery, Snowflake, Azure — not in use, no connectors needed
- Any write-back to source systems — this system never modifies source data
- Real-time/streaming metadata — refresh is scheduled, not live
- Full data quality auditing — this is a dictionary and relationship map, not a DQ framework (may be a future phase)

---

## 4. Core Design Principle

**The LLM never touches production data directly, and never executes anything beyond a validated read.**

Given that our current database credentials carry write permissions and a separate read-only role isn't available from the team, the system is designed so this limitation doesn't matter:

- Production credentials are used **only** by a scheduled extraction script that we write, run, and audit ourselves — never by the LLM or any agent
- That script pulls schema, column statistics, and safely masked/sampled data into a **sandbox database that we create and fully control**, with genuine read-only permissions set by us
- The LLM and all reasoning happens against the sandbox, never against production
- Even the extraction script itself validates every query it runs (see Section 6) as a second layer of protection, in case the script is ever modified or extended later

This means the "no write-permission credential" constraint is solved architecturally rather than by asking for something we can't get.

---

## 5. System Architecture

### Layer 1 — Source connections
- MySQL, PostgreSQL, Redshift connected via existing credential patterns (reusing existing DB helper functions where possible)
- Used only by the scheduled extraction job, never by the LLM

### Layer 2 — Extraction & validation
- Schema pull via `INFORMATION_SCHEMA` (works consistently across all three engines): tables, columns, types, nullability, declared constraints, row counts
- Every query the extraction job runs is parsed and validated before execution (SQL AST check — SELECT/EXPLAIN only, no stacked statements, no SET/DDL/DML)
- Row-count caps and statement timeouts on every query
- Table/column allowlist so the extraction job only touches datasets in scope

### Layer 3 — PII detection & classification
- Every column is scanned before any sampling happens:
  - Name-based heuristics (`email`, `phone`, `dob`, `ssn`, `address`, etc.)
  - Pattern-based checks on sampled values (regex for known formats, entropy checks)
- Every column gets tagged: `public`, `internal`, `sensitive`, or `unknown — needs review`
- Only `public`/`internal` columns get real sample values copied into the sandbox
- `sensitive` and `unknown` columns get column name, type, and statistics only (null %, distinct count) — never raw values, anywhere in the pipeline

### Layer 4 — Sandbox mirror
- A database we own (e.g. local Postgres/DuckDB/SQLite on a host we control), populated by the extraction job on a schedule
- Genuine read-only role for anything that queries it — since we created it, we set this ourselves
- This is the only thing the LLM ever queries

### Layer 5 — LLM reasoning (two distinct, separated tasks)

**Task A — Description generation**
- Given a table/column's schema + statistics (masked where required), the LLM drafts a plain-English description
- Grounded only in what's provided — no external assumptions, no invented business context
- Every description is a draft until reviewed

**Task B — Relationship discovery**
- Structural candidate generation is deterministic code, not the LLM: match column names, types, and cardinality shapes across all tables
- Each candidate is then validated deterministically: what % of non-null values in column A actually exist in column B, checked against real data in the sandbox
- Only validated candidates (above a confidence threshold) are passed to the LLM
- The LLM's only job here is to narrate the confirmed relationship in plain English — it does not get to propose relationships on its own, only explain ones already statistically confirmed

### Layer 6 — Review & publishing
- Every dictionary entry and relationship gets a confidence tier (see Section 8)
- Only high-confidence, low-risk items auto-publish
- Everything else sits in a review queue
- Published output: a searchable internal catalog (dictionary entries + relationship graph), each entry linked back to its source query, sample size, and last-refresh date

---

## 6. Guardrails Summary

| Guardrail | Purpose |
|---|---|
| LLM never receives DB credentials or a free-text SQL execution tool | Removes the LLM as a path to any write, regardless of underlying credential permissions |
| Every query is AST-parsed and validated (SELECT/EXPLAIN only) before execution | Blocks writes, stacked statements, and SET-based bypass attempts |
| Extraction job uses production credentials; LLM only ever queries the sandbox | Production write-capable access touches the system once, in code we control — not through agentic reasoning |
| PII/sensitivity scan runs before any sampling | Prevents sensitive values from ever reaching the LLM, even accidentally |
| Row-count caps and statement timeouts | Prevents runaway or unexpectedly expensive queries |
| Table/column allowlist | Keeps the system scoped to datasets we intend to document |
| Full audit log of every query attempt, including blocked ones | Immediate visibility if anything unexpected is attempted |
| Deterministic validation before any relationship is reported | Prevents the LLM from presenting a guess as a confirmed relationship |
| Confidence-tiered human review queue | Makes review realistic for one part-time reviewer instead of requiring full manual coverage |

---

## 7. Areas & Dimensions Covered

- **Schema documentation** — tables, columns, types, constraints, row counts
- **Semantic documentation** — plain-English descriptions of what each table/column represents
- **Relationship mapping** — declared foreign keys plus statistically discovered undeclared relationships
- **Data sensitivity classification** — every column tagged by PII/sensitivity level
- **Confidence scoring** — every generated description and relationship carries a confidence tier
- **Refresh & versioning** — scheduled re-extraction, with change tracking over time (new tables, changed schemas, dropped columns)
- **Audit trail** — every query, every generated entry, every review decision logged

---

## 8. Review Workflow (Confidence Tiers)

| Tier | Example | Action |
|---|---|---|
| High | Declared FK, clear naming, standard pattern | Auto-published |
| Medium | LLM-generated description, no existing definition to cross-check | Queued for quick approve/edit |
| Low | Relationship candidate with partial overlap or ambiguous naming | Requires manual judgment |
| Flagged | Any column tagged `sensitive` or `unknown` | Always requires sign-off before publishing, even for masked descriptions |

---

## 9. Execution Plan (Phased)

**Phase 1 — Safe extraction pipeline**
Build the extraction job and sandbox mirror. No LLM involved. Goal: prove schema + stats + masked samples can be pulled safely from MySQL, PostgreSQL, and Redshift into our own controlled sandbox.

**Phase 2 — PII detection & classification**
Build and validate the column sensitivity scan against real (but non-critical) datasets first, before trusting it on everything.

**Phase 3 — Description generation**
LLM-generated descriptions for `public`/`internal` columns only, with the review queue in place from day one.

**Phase 4 — Relationship discovery**
Candidate generation + deterministic validation + LLM narration, reviewed before publishing.

**Phase 5 — Catalog & refresh scheduling**
Searchable output, scheduled refresh cadence, change tracking across refreshes.

Each phase is independently useful — Phase 1 alone gives us a safe, reusable extraction pipeline even before any LLM work starts.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Underlying DB credential has write access | Sandbox architecture (Section 4) — LLM never touches production |
| PII missed by automated detection | Conservative default: anything not clearly `public` is treated as `sensitive` until reviewed |
| LLM hallucinated relationship presented as fact | Relationships are deterministically validated before the LLM ever narrates them |
| Review backlog piles up (single part-time reviewer) | Confidence tiering limits manual review to genuinely ambiguous or sensitive cases only |
| Sandbox drifts from production schema | Scheduled refresh with explicit change tracking, not a one-time copy |

---

## 11. Open Decisions

- Where should the sandbox live — local Postgres, DuckDB, or SQLite on the extraction host?
- Refresh cadence — daily, weekly?
- Catalog output — simple internal static site, or an existing tool (e.g. OpenMetadata/DataHub) if broader adoption is expected later?
- PII detection — build a lightweight custom scanner, or use an existing library (e.g. Microsoft Presidio) for pattern detection?

---

## 12. Success Criteria

- Every in-scope table and column has a reviewed, published description
- Relationship graph covers all declared FKs plus newly discovered undeclared relationships, each with a confidence score
- Zero write operations ever reach production through this system (verified via audit log)
- Refresh pipeline runs unattended on schedule without manual intervention
