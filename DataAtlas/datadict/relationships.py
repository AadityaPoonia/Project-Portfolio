"""Phase 4: relationship discovery.

    python -m datadict.relationships [--config sources.yml] [--source NAME]
                                     [--narrate] [--force]

Design contract (design doc, Layer 5 Task B):
- Candidate generation is DETERMINISTIC code: column-name conventions,
  type compatibility, and the destination being a primary-key/unique column.
- Validation is DETERMINISTIC: what fraction of distinct non-null source
  values exist in the destination column. Same-source pairs are checked with
  a guarded count-only join on the live source (only counts cross the wire —
  never values). Cross-source pairs fall back to overlap of sandbox samples
  and are capped at 'low' confidence.
- The LLM's only role (--narrate) is to explain relationships that already
  passed validation. It cannot propose or promote one.

Declared FKs from the extraction run are imported as kind='declared',
confidence high, auto-approved. Discovered ones auto-approve only at
>=99% overlap with a conventional name match; everything else queues
for review.
"""
import argparse
import json
import sys
from dataclasses import dataclass

from sqlalchemy import select

from .audit import AuditLog
from .config import load_config
from .connections import GuardedSource, build_url
from .sandbox import Sandbox, cat_relationships
from .stats import quote_ident

VALIDATE_DISTINCT_LIMIT = 1000   # distinct src values checked per candidate
MIN_OVERLAP_TO_KEEP = 0.5
HIGH_OVERLAP = 0.99
MEDIUM_OVERLAP = 0.85
UNIQUE_RATIO = 0.9               # distinct/rows above this ≈ unique column

_NUMERIC = {"int", "integer", "bigint", "smallint", "tinyint", "mediumint",
            "decimal", "numeric", "float", "double", "real", "double precision"}
_STRINGY = {"varchar", "char", "text", "character varying", "character",
            "uuid", "tinytext", "mediumtext", "longtext"}


@dataclass
class ColRef:
    source: str
    schema: str
    table: str
    column: str

    def key(self) -> tuple:
        return (self.source, self.schema, self.table, self.column)

    def as_dict(self) -> dict:
        return {"source": self.source, "schema": self.schema,
                "table": self.table, "column": self.column}

    def __str__(self) -> str:
        return f"{self.source}:{self.schema}.{self.table}.{self.column}"


@dataclass
class Candidate:
    src: ColRef
    dst: ColRef
    reason: str                  # 'name_convention' | 'same_name'


def coarse_type(data_type: str | None) -> str:
    t = (data_type or "").lower()
    if t in _NUMERIC:
        return "num"
    if t in _STRINGY:
        return "str"
    return "other"


def _singulars(word: str) -> set[str]:
    """users -> {users, user}; matches 'user_id' to table 'users'."""
    out = {word}
    if word.endswith("ies"):
        out.add(word[:-3] + "y")
    if word.endswith("es"):
        out.add(word[:-2])
    if word.endswith("s"):
        out.add(word[:-1])
    return out


def generate_candidates(tables: list[dict], columns: list[dict]) -> list[Candidate]:
    """Deterministic candidate pairs from catalog metadata (no LLM, no I/O)."""
    pk_cols: dict[tuple, list[str]] = {}
    declared: set[tuple] = set()
    row_est: dict[tuple, int | None] = {}
    for t in tables:
        tkey = (t["source"], t["table_schema"], t["table_name"])
        pk_cols[tkey] = json.loads(t["primary_key"] or "[]")
        row_est[tkey] = t["row_estimate"]
        for fk in json.loads(t["foreign_keys"] or "[]"):
            declared.add((t["source"], t["table_schema"], t["table_name"],
                          fk["column"], fk["ref_schema"], fk["ref_table"],
                          fk["ref_column"]))

    # Destination candidates: PK columns, plus unique-looking columns.
    dst_index: dict[str, list[tuple[ColRef, str]]] = {}   # column name -> [(ref, type)]
    table_by_name: dict[str, list[tuple]] = {}
    coltype: dict[tuple, str] = {}
    for c in columns:
        tkey = (c["source"], c["table_schema"], c["table_name"])
        ref = ColRef(c["source"], c["table_schema"], c["table_name"], c["column_name"])
        coltype[ref.key()] = coarse_type(c["data_type"])
        est = row_est.get(tkey)
        is_pk = c["column_name"] in pk_cols.get(tkey, [])
        is_unique = (c["distinct_count"] and est
                     and c["distinct_count"] >= UNIQUE_RATIO * est)
        if is_pk or is_unique:
            dst_index.setdefault(c["column_name"].lower(), []).append(
                (ref, coarse_type(c["data_type"])))
        table_by_name.setdefault(c["table_name"].lower(), []).append(tkey)

    seen: set[tuple] = set()
    out: list[Candidate] = []

    def add(src: ColRef, dst: ColRef, reason: str) -> None:
        if src.key()[:3] == dst.key()[:3]:      # same table
            return
        pair = (src.key(), dst.key())
        if pair in seen:
            return
        if (src.source, src.schema, src.table, src.column,
                dst.schema, dst.table, dst.column) in declared:
            return                               # already a declared FK
        if coltype[src.key()] != coltype.get(dst.key()) \
                or coltype[src.key()] == "other":
            return
        seen.add(pair)
        out.append(Candidate(src, dst, reason))

    for c in columns:
        name = c["column_name"].lower()
        src = ColRef(c["source"], c["table_schema"], c["table_name"], c["column_name"])

        # rule 1: <entity>_id -> table <entity>(s).<pk>
        if name.endswith("_id") and len(name) > 3:
            entity = name[:-3]
            for t in tables:
                if t["table_name"].lower() in _singulars(entity) or \
                        entity in _singulars(t["table_name"].lower()):
                    tkey = (t["source"], t["table_schema"], t["table_name"])
                    for pk in pk_cols.get(tkey, []):
                        add(src, ColRef(*tkey, pk), "name_convention")

        # rule 2: identical column name where the other side is PK/unique.
        # Generic key names (id/uuid/...) are excluded — every table has one
        # and integer id ranges overlap by accident, not by relationship.
        if name not in ("id", "uuid", "guid", "pk", "key"):
            for dst, _dtype in dst_index.get(name, []):
                reason = "same_name" if not name.endswith("_id") else "name_convention"
                add(src, dst, reason)

    return out


# --- deterministic validation ------------------------------------------------

def validate_same_source(guarded: GuardedSource, cand: Candidate,
                         limit: int = VALIDATE_DISTINCT_LIMIT) -> tuple[float, int]:
    """Fraction of (up to `limit`) distinct non-null src values present in dst.
    Count-only query: no raw values are returned, so this is safe to run
    even when the columns themselves are sensitive."""
    k = guarded.engine_kind
    s_col = quote_ident(cand.src.column, k)
    s_tbl = f"{quote_ident(cand.src.schema, k)}.{quote_ident(cand.src.table, k)}"
    d_col = quote_ident(cand.dst.column, k)
    d_tbl = f"{quote_ident(cand.dst.schema, k)}.{quote_ident(cand.dst.table, k)}"
    rows = guarded.fetch(
        f"SELECT COUNT(*) AS n_checked, "
        f"SUM(CASE WHEN d.{d_col} IS NOT NULL THEN 1 ELSE 0 END) AS n_matched "
        f"FROM (SELECT DISTINCT {s_col} AS v FROM {s_tbl} "
        f"      WHERE {s_col} IS NOT NULL LIMIT {int(limit)}) s "
        f"LEFT JOIN {d_tbl} d ON d.{d_col} = s.v")
    n = int(rows[0]["n_checked"] or 0)
    if n == 0:
        return 0.0, 0
    return int(rows[0]["n_matched"] or 0) / n, n


def sample_overlap(sandbox: Sandbox, run_ids: dict[str, str],
                   cand: Candidate) -> tuple[float, int] | None:
    """Cross-source fallback: overlap of sandbox sample values. Returns None
    when either side wasn't sampled (e.g. sensitive columns)."""
    def values(ref: ColRef) -> set[str] | None:
        sample = sandbox.samples_for_run(run_ids[ref.source], ref.table)
        if not sample or ref.column not in json.loads(sample["sampled_columns"]):
            return None
        return {r[ref.column] for r in json.loads(sample["rows"])
                if r.get(ref.column) is not None}

    src_vals, dst_vals = values(cand.src), values(cand.dst)
    if not src_vals or dst_vals is None:
        return None
    return len(src_vals & dst_vals) / len(src_vals), len(src_vals)


def confidence_for(overlap: float, method: str, reason: str) -> str:
    if method == "sample_overlap":
        return "low"                      # 100-row samples can't prove more
    if overlap >= HIGH_OVERLAP and reason == "name_convention":
        return "high"
    if overlap >= MEDIUM_OVERLAP:
        return "medium"
    return "low"


_NARRATE_SYSTEM = """You explain ALREADY-VALIDATED database relationships for a data dictionary.
You will get two column references and the measured value-overlap. The relationship is confirmed;
your job is only to state, in one or two plain-English sentences, what it means for joining these
tables. Do not speculate beyond the given names and numbers.
Return JSON: {"narration": "..."}"""


def _existing_run_ids(sandbox: Sandbox) -> set[str]:
    with sandbox.engine.connect() as conn:
        rows = conn.execute(select(cat_relationships.c.run_id).distinct()).all()
    return {r[0] for r in rows}


def discover(sandbox: Sandbox, app, only_source: str | None,
             narrate_fn=None, force: bool = False) -> int:
    cfgs = {s.name: s for s in app.sources
            if not only_source or s.name == only_source}
    run_ids: dict[str, str] = {}
    for name in cfgs:
        rid = sandbox.latest_run(name)
        if rid:
            run_ids[name] = rid
        else:
            print(f"[{name}] no successful extraction run — skipping", file=sys.stderr)
    if not run_ids:
        return 0

    already = _existing_run_ids(sandbox)
    if not force and all(rid in already for rid in run_ids.values()):
        print("relationships already discovered for these runs (use --force to redo)")
        return 0

    tables, columns = [], []
    for name, rid in run_ids.items():
        tables += sandbox.tables_for_run(rid)
        columns += sandbox.columns_for_run(rid)

    n_written = 0
    # 1. declared FKs -> high confidence, auto-approved
    for t in tables:
        for fk in json.loads(t["foreign_keys"] or "[]"):
            src = ColRef(t["source"], t["table_schema"], t["table_name"], fk["column"])
            dst = ColRef(t["source"], fk["ref_schema"], fk["ref_table"], fk["ref_column"])
            sandbox.add_relationship(
                run_ids[t["source"]], "declared", src.as_dict(), dst.as_dict(),
                method="declared_fk", overlap_frac=None, n_checked=None,
                confidence="high",
                status="approved" if fk.get("enforced", True) else "pending")
            n_written += 1

    # 2. discovered candidates, deterministically validated
    candidates = generate_candidates(tables, columns)
    print(f"{len(candidates)} candidate(s) from name/type/uniqueness rules")

    guarded: dict[str, GuardedSource] = {}
    audit = AuditLog(app.audit_log_path)
    try:
        for cand in candidates:
            if cand.src.source == cand.dst.source:
                cfg = cfgs[cand.src.source]
                if cand.src.source not in guarded:
                    creds = cfg.credentials()
                    guarded[cfg.name] = GuardedSource(
                        cfg.name, cfg.engine,
                        build_url(cfg.engine, creds["user"], creds["password"],
                                  creds["host"], creds["port"], creds["database"]),
                        audit, row_cap=cfg.row_cap, timeout_s=cfg.timeout_s,
                        run_id=run_ids[cfg.name])
                overlap, n = validate_same_source(guarded[cand.src.source], cand)
                method = "join_overlap"
            else:
                result = sample_overlap(sandbox, run_ids, cand)
                if result is None:
                    continue
                overlap, n = result
                method = "sample_overlap"

            if n == 0 or overlap < MIN_OVERLAP_TO_KEEP:
                continue
            conf = confidence_for(overlap, method, cand.reason)
            status = "approved" if conf == "high" else "pending"

            narration = None
            if narrate_fn:
                user = json.dumps({"from": str(cand.src), "to": str(cand.dst),
                                   "overlap": f"{overlap:.1%} of {n} distinct values",
                                   "match_rule": cand.reason})
                narration = str(narrate_fn(_NARRATE_SYSTEM, user).get("narration", "")).strip() or None

            sandbox.add_relationship(
                run_ids[cand.src.source], "discovered",
                cand.src.as_dict(), cand.dst.as_dict(), method=method,
                overlap_frac=round(overlap, 4), n_checked=n,
                confidence=conf, status=status, narration=narration)
            n_written += 1
            print(f"  {cand.src} -> {cand.dst}: {overlap:.0%} of {n} "
                  f"({conf}, {status})")
    finally:
        for g in guarded.values():
            g.dispose()
    return n_written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relationship discovery (Phase 4)")
    parser.add_argument("--config", default="sources.yml")
    parser.add_argument("--source", help="only this source name")
    parser.add_argument("--narrate", action="store_true",
                        help="add LLM narration to validated relationships")
    parser.add_argument("--force", action="store_true",
                        help="re-discover even if these runs were already processed")
    args = parser.parse_args(argv)

    app = load_config(args.config)
    sandbox = Sandbox(app.sandbox_url)
    narrate_fn = None
    if args.narrate:
        from .llm import LLMClient
        narrate_fn = LLMClient().complete_json

    n = discover(sandbox, app, args.source, narrate_fn, args.force)
    print(f"\nstored {n} relationship(s); review with: "
          f"python -m datadict.review list --what relationships")
    return 0


if __name__ == "__main__":
    sys.exit(main())
