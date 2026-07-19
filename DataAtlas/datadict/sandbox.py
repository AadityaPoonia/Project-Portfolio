"""Sandbox catalog: the only thing the LLM (Phase 3+) will ever query.

A metadata mirror, not a data copy: tables/columns/stats plus small
JSON sample sets. Target is any SQLAlchemy URL (Postgres in production —
it has real GRANT-based read-only roles; SQLite works for local dev).

Each extraction run is versioned via extraction_runs; rows carry run_id
so refreshes append history instead of clobbering it. Change tracking
across runs (new/dropped/changed tables) diffs on top of this.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    create_engine, MetaData, Table as SATable, Column as SACol,
    String, Integer, Float, Text, Boolean, DateTime, select, and_,
)
from sqlalchemy.engine import make_url

metadata = MetaData()

extraction_runs = SATable(
    "extraction_runs", metadata,
    SACol("run_id", String(36), primary_key=True),
    SACol("source", String(128), nullable=False),
    SACol("started_at", DateTime(timezone=True), nullable=False),
    SACol("finished_at", DateTime(timezone=True)),
    SACol("status", String(16), nullable=False, default="running"),
    SACol("tables_extracted", Integer),
    SACol("error", Text),
)

cat_tables = SATable(
    "cat_tables", metadata,
    SACol("id", Integer, primary_key=True, autoincrement=True),
    SACol("run_id", String(36), nullable=False, index=True),
    SACol("source", String(128), nullable=False),
    SACol("table_schema", String(128), nullable=False),
    SACol("table_name", String(256), nullable=False),
    SACol("row_estimate", Integer),
    SACol("primary_key", Text),          # JSON list
    SACol("foreign_keys", Text),         # JSON list of dicts
)

cat_columns = SATable(
    "cat_columns", metadata,
    SACol("id", Integer, primary_key=True, autoincrement=True),
    SACol("run_id", String(36), nullable=False, index=True),
    SACol("source", String(128), nullable=False),
    SACol("table_schema", String(128), nullable=False),
    SACol("table_name", String(256), nullable=False),
    SACol("column_name", String(256), nullable=False),
    SACol("ordinal", Integer),
    SACol("data_type", String(128)),
    SACol("is_nullable", Boolean),
    SACol("column_default", Text),
    SACol("sensitivity", String(16), nullable=False),
    SACol("null_frac", Float),
    SACol("distinct_count", Integer),
    SACol("min_value", Text),
    SACol("max_value", Text),
    SACol("top_values", Text),           # JSON list [{value,count}]
    SACol("stats_skipped_reason", Text),
)

# Phase 3: LLM-drafted descriptions. Everything lands as status='pending'
# (or 'flagged' tier for sensitive/unknown columns) and is only surfaced by
# search/export once a human moves it to 'approved' via the review CLI.
cat_descriptions = SATable(
    "cat_descriptions", metadata,
    SACol("id", Integer, primary_key=True, autoincrement=True),
    SACol("run_id", String(36), nullable=False, index=True),   # extraction run described
    SACol("source", String(128), nullable=False),
    SACol("table_schema", String(128), nullable=False),
    SACol("table_name", String(256), nullable=False),
    SACol("column_name", String(256)),   # NULL -> table-level description
    SACol("description", Text, nullable=False),
    SACol("model", String(64)),
    SACol("tier", String(16), nullable=False),      # high | medium | low | flagged
    SACol("status", String(16), nullable=False, default="pending"),
    #     pending | approved | rejected
    SACol("reviewer_note", Text),
    SACol("created_at", DateTime(timezone=True), nullable=False),
    SACol("reviewed_at", DateTime(timezone=True)),
)

# Phase 4: relationships. Declared FKs are imported as kind='declared'
# (auto-approved, per the design's confidence tiers); discovered candidates
# must pass deterministic value-overlap validation before landing here.
cat_relationships = SATable(
    "cat_relationships", metadata,
    SACol("id", Integer, primary_key=True, autoincrement=True),
    SACol("run_id", String(36), nullable=False, index=True),
    SACol("kind", String(16), nullable=False),      # declared | discovered
    SACol("src_source", String(128), nullable=False),
    SACol("src_schema", String(128), nullable=False),
    SACol("src_table", String(256), nullable=False),
    SACol("src_column", String(256), nullable=False),
    SACol("dst_source", String(128), nullable=False),
    SACol("dst_schema", String(128), nullable=False),
    SACol("dst_table", String(256), nullable=False),
    SACol("dst_column", String(256), nullable=False),
    SACol("method", String(32)),        # declared_fk | join_overlap | sample_overlap
    SACol("overlap_frac", Float),       # matched / checked distinct values
    SACol("n_checked", Integer),
    SACol("confidence", String(16), nullable=False),  # high | medium | low
    SACol("narration", Text),           # LLM plain-English explanation (optional)
    SACol("status", String(16), nullable=False, default="pending"),
    #     pending | approved | rejected
    SACol("reviewer_note", Text),
    SACol("created_at", DateTime(timezone=True), nullable=False),
    SACol("reviewed_at", DateTime(timezone=True)),
)

cat_samples = SATable(
    "cat_samples", metadata,
    SACol("id", Integer, primary_key=True, autoincrement=True),
    SACol("run_id", String(36), nullable=False, index=True),
    SACol("source", String(128), nullable=False),
    SACol("table_schema", String(128), nullable=False),
    SACol("table_name", String(256), nullable=False),
    SACol("sampled_columns", Text),      # JSON list of column names
    SACol("rows", Text),                 # JSON list of row dicts
    SACol("sample_size", Integer),
)


class Sandbox:
    def __init__(self, url: str):
        u = make_url(url)
        if u.get_backend_name() == "sqlite" and u.database:
            # SQLite creates the file but not its parent directory.
            Path(u.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url)
        metadata.create_all(self.engine)

    def start_run(self, source: str) -> str:
        run_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(extraction_runs.insert().values(
                run_id=run_id, source=source,
                started_at=datetime.now(timezone.utc), status="running",
            ))
        return run_id

    def finish_run(self, run_id: str, status: str, tables_extracted: int,
                   error: str | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                extraction_runs.update()
                .where(extraction_runs.c.run_id == run_id)
                .values(finished_at=datetime.now(timezone.utc), status=status,
                        tables_extracted=tables_extracted, error=error)
            )

    def write_table(self, run_id: str, source: str, table, col_stats: dict,
                    sampled_columns: list[str], sample_rows: list[dict]) -> None:
        """Persist one extracted table (schema + stats + samples) atomically."""
        with self.engine.begin() as conn:
            conn.execute(cat_tables.insert().values(
                run_id=run_id, source=source,
                table_schema=table.schema, table_name=table.name,
                row_estimate=table.row_estimate,
                primary_key=json.dumps(table.primary_key),
                foreign_keys=json.dumps([vars(fk) for fk in table.foreign_keys]),
            ))
            for col in table.columns:
                st = col_stats.get(col.name)
                conn.execute(cat_columns.insert().values(
                    run_id=run_id, source=source,
                    table_schema=table.schema, table_name=table.name,
                    column_name=col.name, ordinal=col.ordinal,
                    data_type=col.data_type, is_nullable=col.is_nullable,
                    column_default=col.default, sensitivity=col.sensitivity,
                    null_frac=st.null_frac if st else None,
                    distinct_count=st.distinct_count if st else None,
                    min_value=st.min_value if st else None,
                    max_value=st.max_value if st else None,
                    top_values=json.dumps(st.top_values) if st else None,
                    stats_skipped_reason=st.skipped_reason if st else None,
                ))
            if sample_rows:
                conn.execute(cat_samples.insert().values(
                    run_id=run_id, source=source,
                    table_schema=table.schema, table_name=table.name,
                    sampled_columns=json.dumps(sampled_columns),
                    rows=json.dumps(sample_rows),
                    sample_size=len(sample_rows),
                ))

    # ---- read helpers (Phases 3-5 consume extraction runs through these) ----

    def latest_run(self, source: str) -> str | None:
        """run_id of the most recent successful extraction for a source."""
        with self.engine.connect() as conn:
            row = conn.execute(
                select(extraction_runs.c.run_id)
                .where(and_(extraction_runs.c.source == source,
                            extraction_runs.c.status == "success"))
                .order_by(extraction_runs.c.started_at.desc())
                .limit(1)).first()
        return row[0] if row else None

    def sources(self) -> list[str]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(extraction_runs.c.source).distinct()).all()
        return [r[0] for r in rows]

    def run_history(self, source: str) -> list[str]:
        """Successful run_ids for a source, newest first."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(extraction_runs.c.run_id)
                .where(and_(extraction_runs.c.source == source,
                            extraction_runs.c.status == "success"))
                .order_by(extraction_runs.c.started_at.desc())).all()
        return [r[0] for r in rows]

    def tables_for_run(self, run_id: str) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(cat_tables).where(cat_tables.c.run_id == run_id)).mappings().all()
        return [dict(r) for r in rows]

    def columns_for_run(self, run_id: str, table_name: str | None = None) -> list[dict]:
        q = select(cat_columns).where(cat_columns.c.run_id == run_id)
        if table_name:
            q = q.where(cat_columns.c.table_name == table_name)
        with self.engine.connect() as conn:
            rows = conn.execute(q.order_by(cat_columns.c.table_name,
                                           cat_columns.c.ordinal)).mappings().all()
        return [dict(r) for r in rows]

    def samples_for_run(self, run_id: str, table_name: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(cat_samples).where(and_(
                    cat_samples.c.run_id == run_id,
                    cat_samples.c.table_name == table_name))).mappings().first()
        return dict(row) if row else None

    # ---- Phase 3/4 writers + shared review-queue transitions ----

    def add_description(self, run_id: str, source: str, schema: str, table: str,
                        column: str | None, description: str, model: str,
                        tier: str, status: str = "pending") -> None:
        with self.engine.begin() as conn:
            conn.execute(cat_descriptions.insert().values(
                run_id=run_id, source=source, table_schema=schema,
                table_name=table, column_name=column, description=description,
                model=model, tier=tier, status=status,
                created_at=datetime.now(timezone.utc)))

    def described_tables(self, source: str) -> set[str]:
        """Tables of a source that already carry non-rejected descriptions
        (any run) — refreshes must not re-bill the LLM for unchanged tables."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(cat_descriptions.c.table_name).distinct()
                .where(and_(cat_descriptions.c.source == source,
                            cat_descriptions.c.status != "rejected"))).all()
        return {r[0] for r in rows}

    def add_relationship(self, run_id: str, kind: str, src: dict, dst: dict,
                         method: str, overlap_frac: float | None,
                         n_checked: int | None, confidence: str,
                         status: str, narration: str | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(cat_relationships.insert().values(
                run_id=run_id, kind=kind,
                src_source=src["source"], src_schema=src["schema"],
                src_table=src["table"], src_column=src["column"],
                dst_source=dst["source"], dst_schema=dst["schema"],
                dst_table=dst["table"], dst_column=dst["column"],
                method=method, overlap_frac=overlap_frac, n_checked=n_checked,
                confidence=confidence, status=status, narration=narration,
                created_at=datetime.now(timezone.utc)))

    def review_item(self, what: str, item_id: int, status: str,
                    note: str | None = None, new_text: str | None = None) -> bool:
        """Approve/reject one description or relationship. Returns False if
        no such id. `new_text` lets the reviewer fix a description inline."""
        tbl = {"description": cat_descriptions, "relationship": cat_relationships}[what]
        values = {"status": status, "reviewed_at": datetime.now(timezone.utc)}
        if note:
            values["reviewer_note"] = note
        if new_text and what == "description":
            values["description"] = new_text
        with self.engine.begin() as conn:
            res = conn.execute(tbl.update().where(tbl.c.id == item_id).values(**values))
        return res.rowcount > 0
