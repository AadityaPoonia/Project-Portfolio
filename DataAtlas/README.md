# DataAtlas

**An LLM-assisted data dictionary and relationship mapper: it charts what data
exists, explains every column in plain English, and maps how tables connect.**

## What this project is

DataAtlas is an internal system that connects to our databases (MySQL, PostgreSQL, Redshift),
automatically documents every table and column in plain English, discovers how
tables join to each other, and publishes it all as a searchable catalog — so
"what does this column mean / how do I join these tables" stops being tribal
knowledge. Full design rationale: `data_dictionary_project_design.md`.

What you get out of it:

| Output | What it is | Where it lives |
|---|---|---|
| Sandbox catalog | Schema, stats, masked samples, descriptions, relationships for every dataset | the database at `SANDBOX_DB_URL` (SQLite file `sandbox/catalog.db` by default) |
| `catalog.html` | Self-contained searchable web page — the human-facing dictionary | project root; open in any browser |
| Audit log | Every single query ever sent to a production database | `logs/audit.jsonl` |

## How it works (the pipeline)

```
 production DBs          EC2 (this project)                        humans
┌──────────────┐   1 extract   ┌─────────────┐   3 describe   ┌────────────┐
│ MySQL/PG/RS  │ ────────────> │   sandbox   │ ─── LLM ────>  │   review   │
│ (read-only,  │   2 discover  │   catalog   │    drafts      │   queue    │
│  guarded)    │ <───validate──│  (we own it)│ <── approve ── │            │
└──────────────┘               └─────────────┘                └────────────┘
                                      │ 4 export
                                      v
                                catalog.html
```

1. **Extract** (`run_extraction`) — pulls schema, statistics, and samples into
   the sandbox. Every column is sensitivity-classified twice: by name
   (`classify.py`) and by scanning actual sampled values for PII patterns
   (`pii_scan.py`). Sensitive/unknown columns never have raw values copied
   anywhere — only shape stats (null %, distinct count).
2. **Discover relationships** (`relationships`) — imports declared foreign
   keys, then proposes extra join candidates from naming conventions
   (`user_id` → `users.id`) and uniqueness stats, and validates every
   candidate against real data (what % of values actually match) before
   storing it with a confidence level.
3. **Describe** (`describe`) — an LLM (OpenAI) reads the masked metadata from
   the sandbox — never the real databases — and drafts descriptions. Every
   draft lands in a review queue; nothing publishes without human approval.
4. **Publish** (`search export`) — builds `catalog.html` from approved
   content only.

### Security model (why this is safe to run against production)

- Production credentials are used ONLY by the extraction/validation jobs —
  never by the LLM, which only ever sees the sandbox.
- Every query to production goes through a guard
  (`connections.py::GuardedSource.fetch`): AST-validated (single SELECT only —
  DML/DDL/SET/stacked statements rejected), row-capped, statement-timeouted,
  and written to the audit log (allowed, blocked, or errored).
- PII protection is escalate-only: a pattern hit makes a column MORE
  restricted; only a human `column_overrides` entry can relax it.
- Relationship validation queries return counts only, never values.
- `tests/test_query_guard.py` is the security spec; `tests/test_pipeline_pii.py`
  pins the guarantee that PII under an innocent column name never reaches the
  sandbox.

## Every file and folder

```
datadict/                    the application
  config.py                  reads sources.yml + .env into config objects
  connections.py             DB engines + the guarded read-only query path
  query_guard.py             SQL AST validator (SELECT-only enforcement)
  audit.py                   append-only query audit log (logs/audit.jsonl)
  schema_extract.py          tables/columns/PKs/FKs per engine (pg_catalog on
                             Postgres — information_schema hides keys from
                             read-only users there)
  classify.py                column sensitivity by NAME (public/internal/
                             sensitive/unknown; unknown == sensitive downstream)
  pii_scan.py                column sensitivity by VALUES (emails, phones,
                             Aadhaar/PAN/SSN, Luhn-valid cards, IPs, JWTs,
                             AWS keys, high-entropy secrets)
  stats.py                   per-column stats, tier-aware (no min/max/top-k
                             for sensitive; never top-k on free text)
  sampling.py                sample rows — SELECT list built from allowed
                             columns only
  sandbox.py                 sandbox catalog schema + all read/write helpers
  run_extraction.py          CLI: phase 1+2 (extract + PII scan)
  relationships.py           CLI: phase 4 (candidates + validation + narration)
  describe.py                CLI: phase 3 (LLM drafts -> review queue)
  review.py                  CLI: approve/reject/edit drafts, bulk approve
  search.py                  CLI: find/show/export the catalog
  changes.py                 CLI: diff two extraction runs (schema drift)
  llm.py                     the only file that talks to OpenAI

tests/                       122 tests; run with pytest (no DB/API needed)
sources.yml                  WHAT to extract (per-dataset config) — gitignored
.env                         SECRETS (DB credentials, OpenAI key) — gitignored
sources.example.yml          templates for the two above
.env.example
refresh.sh                   the whole pipeline in one script (for cron)
requirements.txt             python dependencies
sandbox/catalog.db           the sandbox (created on first run) — gitignored
logs/audit.jsonl             the audit log (created on first run) — gitignored
catalog.html                 the published dictionary (created by export)
```

Sandbox tables: `extraction_runs` (run history), `cat_tables`, `cat_columns`,
`cat_samples` (schema/stats/samples per run), `cat_descriptions`,
`cat_relationships` (drafts + review status). Runs append — history is never
overwritten, which is what makes `changes` diffing possible.

## Setup from scratch (once per machine)

Runs on the analytics EC2 (sources are only reachable from inside the VPC/VPN).

```bash
cd ~/data-dictionary                     # the project folder
python3 -m venv .venv                    # if missing: sudo apt install python3-venv
.venv/bin/pip install -r requirements.txt
cp sources.example.yml sources.yml       # then edit (see next section)
cp .env.example .env                     # then edit; keep it private:
chmod 600 .env
.venv/bin/python -m pytest tests/ -q     # expect: all passing, no DB needed
```

## Adding / editing datasets

Each dataset = one block in `sources.yml` + one credential set in `.env`,
linked by `env_prefix`. No code changes ever.

**`sources.yml`:**
```yaml
sources:
  - name: gl_ai_agent          # any unique name; used in --source and the catalog
    engine: postgres           # mysql | postgres | redshift
    env_prefix: GLAI_DB        # -> reads GLAI_DB_HOST etc. from .env
    schemas: [public]          # which schemas to document
    # table_allowlist:         # omit entirely = ALL tables in those schemas
    #   public: [users, threads]     # or: only these tables
    # column_overrides:        # human ruling on sensitivity (wins over all scanners)
    #   course_code: public
    sample_size: 100           # rows sampled per table (optional, default 100)
    row_cap: 10000             # hard cap on any query result (optional)
    timeout_s: 60              # per-query timeout (optional)
```

**`.env`:** add the five variables for that prefix:
```
GLAI_DB_HOST=...    GLAI_DB_PORT=5432    GLAI_DB_USER=...
GLAI_DB_PASSWORD=...    GLAI_DB_NAME=...
```

If a variable is missing, the job exits immediately naming exactly which ones.
Always request a **read-only** DB user; the query guard protects us either way.

## Running it — start to end

```bash
PY=.venv/bin/python

# 0. connectivity + scope check: connects, lists tables, writes NOTHING
$PY -m datadict.run_extraction --dry-run

# 1. extract everything into the sandbox (~minutes)
$PY -m datadict.run_extraction

# 2. discover + validate relationships
$PY -m datadict.relationships              # --narrate adds LLM explanations

# 3. draft descriptions with the LLM (needs OPENAI_API_KEY in .env)
$PY -m datadict.describe --limit 3         # sanity-check on 3 tables first
$PY -m datadict.describe                   # then everything

# 4. review: read drafts, then approve/fix/reject
$PY -m datadict.review list                          # pending descriptions
$PY -m datadict.review list --what relationships     # pending relationships
$PY -m datadict.review approve 12                    # one item, by id
$PY -m datadict.review approve 13 --edit "Better wording."
$PY -m datadict.review reject 14 --note "wrong"
$PY -m datadict.review approve-all                   # all EXCEPT flagged tier
$PY -m datadict.review approve-all --tier flagged --table threads  # flagged, deliberately

# 5. publish the catalog (approved content only)
$PY -m datadict.search export --out catalog.html

# any time: query the catalog from the terminal
$PY -m datadict.search find enrollment
$PY -m datadict.search show threads

# after a re-extraction: what changed in the source schemas?
$PY -m datadict.changes
```

### Ways to run it

- **Everything vs one dataset**: every pipeline command takes
  `--source NAME` (e.g. `--source gl_ai_agent`); without it, all configured
  datasets are processed one after another.
- **One shot**: `./refresh.sh` runs extract → changes → relationships →
  describe → export in order.
- **On a schedule** (the end-state): `crontab -e` and add
  `0 3 * * 1 cd /home/gl_aaditya/data-dictionary && ./refresh.sh >> logs/refresh.log 2>&1`
  (weekly, Monday 03:00). Refreshes are cheap: already-described tables and
  already-processed runs are skipped, so an unchanged week costs no LLM tokens.
- **Redo something**: `describe --force --table X` re-drafts one table;
  `relationships --force` re-discovers for the current runs.

### Review tiers (what the labels mean)

| Tier | Meaning | Handling |
|---|---|---|
| high | declared FK or ≥99% validated with conventional naming | auto-approved |
| medium | ordinary LLM draft | `approve-all` covers it |
| low | partial overlap / weak evidence | look before approving |
| flagged | column is sensitive/unknown | excluded from `approve-all` unless `--tier flagged` |

## Developing from a laptop

Code is edited locally and synced to the EC2 (nothing runs locally — sources
are VPN-only). After any local change:

```bash
rsync -av -e "ssh -i ~/path/to/key.pem" \
  --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude 'sandbox' --exclude 'logs' --exclude '.env' \
  ~/Documents/data-dictionary/ USER@EC2_HOST:~/data-dictionary/
```

The excludes matter: never overwrite the EC2's `.env` (real secrets),
`sandbox/` (extraction history), or `logs/` (audit trail). Copy the catalog
back to view it: `scp ... USER@EC2_HOST:~/data-dictionary/catalog.html ~/Downloads/`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `--dry-run` hangs then times out | EC2 can't reach the DB host/port — security group or VPN routing, not credentials |
| `missing env vars [...]` | add the named variables to `.env` (prefix must match `env_prefix`) |
| `0 tables in scope` | tables live in a different schema — fix `schemas:` in sources.yml |
| `ensurepip is not available` during venv creation | `sudo apt install python3-venv`, recreate the venv |
| venv errors after copying the project | never copy `.venv` between machines; `rm -rf .venv` and rebuild |
| column wrongly escalated to sensitive | it's conservative by design; overrule with `column_overrides: {col_name: public}` and re-extract |
| empty PKs/FKs on Postgres | fixed — extraction uses `pg_catalog`, not the owner-filtered `information_schema` views |
| OpenAI errors in `describe` | check `OPENAI_API_KEY` in `.env`; model is `OPENAI_MODEL` (default gpt-4o-mini) |

## Tests

```bash
.venv/bin/python -m pytest tests/ -q     # 122 tests, no DB or API key needed
```

`test_query_guard.py` = security spec (must-never-reach-production cases).
`test_pipeline_pii.py` = the PII-never-leaks guarantee, end to end.

