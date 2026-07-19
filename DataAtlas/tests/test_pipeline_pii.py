"""End-to-end Phase 1+2 guarantee: a column whose NAME looks safe (so the
name classifier allows sampling) but whose VALUES contain PII is escalated
during extraction, and neither its sample values nor value-stats ever
reach the sandbox.

(A column with an unrecognised name is 'unknown' and never sampled at all —
that path is already covered by the Phase 1 tests. The value scanner exists
exactly for the innocent-name case tested here.)
"""
import json

import pytest
from sqlalchemy import text

from datadict.audit import AuditLog
from datadict.config import SourceConfig
from datadict.run_extraction import process_source
from datadict.sandbox import Sandbox


@pytest.fixture
def fake_source(tmp_path, monkeypatch):
    """A sqlite DB posing as a mysql source. 'feedback_type' name-classifies
    as internal (matches 'type') but actually holds email addresses."""
    monkeypatch.setattr("datadict.connections._connect_args", lambda *a: {})
    db = f"sqlite:///{tmp_path}/src.db"
    monkeypatch.setattr("datadict.run_extraction.build_url", lambda *a, **k: db)
    monkeypatch.setattr(SourceConfig, "credentials", lambda self: {
        "host": "x", "port": 0, "user": "x", "password": "x", "database": "x"})

    from sqlalchemy import create_engine
    eng = create_engine(db)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE feedback "
                          "(id INTEGER PRIMARY KEY, status TEXT, feedback_type TEXT)"))
        for i in range(20):
            conn.execute(text("INSERT INTO feedback VALUES (:i, 'active', :v)"),
                         {"i": i, "v": f"learner{i}@example.com"})
    eng.dispose()
    return db


def _fake_schema_extract(source, schema, allowset):
    from datadict.schema_extract import Table, Column
    t = Table(schema="main", name="feedback", row_estimate=20)
    t.columns = [Column("id", "integer", False, 1),
                 Column("status", "varchar", True, 2),
                 Column("feedback_type", "varchar", True, 3)]
    t.primary_key = ["id"]
    return [t]


def test_pii_in_values_never_reaches_sandbox(fake_source, tmp_path, monkeypatch):
    monkeypatch.setattr("datadict.run_extraction.extract_schema", _fake_schema_extract)
    cfg = SourceConfig(name="demo", engine="mysql", env_prefix="X",
                       schemas=["main"], sample_size=10)
    sandbox = Sandbox(f"sqlite:///{tmp_path}/catalog.db")
    audit = AuditLog(str(tmp_path / "audit.jsonl"))

    n = process_source(cfg, sandbox, audit, dry_run=False)
    assert n == 1

    with sandbox.engine.connect() as conn:
        cols = {r["column_name"]: dict(r) for r in conn.execute(
            text("SELECT * FROM cat_columns")).mappings()}
        samples = conn.execute(text("SELECT * FROM cat_samples")).mappings().all()

    # name heuristics said 'internal'; the value scan must overrule to sensitive
    assert cols["feedback_type"]["sensitivity"] == "sensitive"
    assert "pii_scan:email" in (cols["feedback_type"]["stats_skipped_reason"] or "")
    # no value-bearing stats for the escalated column
    assert cols["feedback_type"]["min_value"] is None
    assert not cols["feedback_type"]["top_values"] or \
        cols["feedback_type"]["top_values"] == "[]"
    # shape stats are still allowed
    assert cols["feedback_type"]["null_frac"] is not None

    # sampled rows exist for the safe columns and carry no trace of the emails
    assert len(samples) == 1
    assert json.loads(samples[0]["sampled_columns"]) == ["id", "status"]
    assert "@example.com" not in samples[0]["rows"]


def test_human_override_is_respected(fake_source, tmp_path, monkeypatch):
    """column_overrides is a deliberate human decision — the scanner must
    not second-guess a column a reviewer explicitly marked public."""
    monkeypatch.setattr("datadict.run_extraction.extract_schema", _fake_schema_extract)
    cfg = SourceConfig(name="demo", engine="mysql", env_prefix="X",
                       schemas=["main"], sample_size=10,
                       column_overrides={"feedback_type": "public"})
    sandbox = Sandbox(f"sqlite:///{tmp_path}/catalog2.db")
    audit = AuditLog(str(tmp_path / "audit2.jsonl"))

    process_source(cfg, sandbox, audit, dry_run=False)
    with sandbox.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT sensitivity FROM cat_columns WHERE column_name='feedback_type'"
        )).mappings().one()
    assert row["sensitivity"] == "public"
