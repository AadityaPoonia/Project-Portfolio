"""End-to-end tests of the guarded execution path and the sandbox writer.

Uses SQLite as the backing store (no server needed). The guard still parses
with the real MySQL dialect — simple SELECTs are dialect-portable — so this
exercises the actual validate -> execute -> cap -> audit chain, including
the core guarantee: a write attempt is blocked, audited, and touches nothing.
"""
import json

import pytest
from sqlalchemy import text

from datadict.audit import AuditLog
from datadict.connections import GuardedSource
from datadict.query_guard import QueryBlocked
from datadict.sandbox import Sandbox
from datadict.schema_extract import Table, Column, ForeignKey
from datadict.stats import ColumnStats


@pytest.fixture
def guarded(tmp_path, monkeypatch):
    # sqlite accepts no mysql driver args; strip them for the test engine only
    monkeypatch.setattr("datadict.connections._connect_args", lambda *a: {})
    audit_path = tmp_path / "audit.jsonl"
    src = GuardedSource("demo", "mysql", f"sqlite:///{tmp_path}/demo.db",
                        AuditLog(str(audit_path)), row_cap=5)
    with src._engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, status TEXT)"))
        for i in range(20):
            conn.execute(text("INSERT INTO users VALUES (:i, 'active')"), {"i": i})
    yield src, audit_path
    src.dispose()


def _audit_events(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class TestGuardedExecution:
    def test_select_runs_and_is_row_capped(self, guarded):
        src, audit_path = guarded
        rows = src.fetch("SELECT id, status FROM users")
        assert len(rows) == 5  # row_cap, though table has 20
        assert rows[0]["status"] == "active"
        ev = _audit_events(audit_path)[-1]
        assert ev["status"] == "allowed" and ev["rows"] == 5

    def test_write_is_blocked_audited_and_data_untouched(self, guarded):
        src, audit_path = guarded
        with pytest.raises(QueryBlocked):
            src.fetch("DELETE FROM users")
        ev = _audit_events(audit_path)[-1]
        assert ev["status"] == "blocked" and "Delete" in ev["error"]
        assert len(src.fetch("SELECT id FROM users LIMIT 3")) == 3  # data intact

    def test_stacked_injection_blocked(self, guarded):
        src, audit_path = guarded
        with pytest.raises(QueryBlocked):
            src.fetch("SELECT 1; DROP TABLE users")
        assert _audit_events(audit_path)[-1]["status"] == "blocked"


class TestSandbox:
    def test_write_and_read_back_full_table(self, tmp_path):
        sb = Sandbox(f"sqlite:///{tmp_path}/catalog.db")
        run_id = sb.start_run("demo")

        table = Table(schema="ops", name="enrollments", row_estimate=1234)
        table.columns = [
            Column("id", "bigint", False, 1, sensitivity="internal"),
            Column("learner_email", "varchar", True, 2, sensitivity="sensitive"),
        ]
        table.primary_key = ["id"]
        table.foreign_keys = [ForeignKey("course_id", "ops", "courses", "id")]

        stats = {
            "id": ColumnStats("id", null_frac=0.0, distinct_count=1234,
                              min_value="1", max_value="1234"),
            "learner_email": ColumnStats("learner_email", null_frac=0.02,
                                         distinct_count=1200),
        }
        sb.write_table(run_id, "demo", table, stats,
                       sampled_columns=["id"], sample_rows=[{"id": "1"}, {"id": "2"}])
        sb.finish_run(run_id, "success", 1)

        with sb.engine.connect() as conn:
            run = conn.execute(text("SELECT * FROM extraction_runs")).mappings().one()
            assert run["status"] == "success" and run["tables_extracted"] == 1

            cols = conn.execute(text(
                "SELECT column_name, sensitivity, min_value FROM cat_columns "
                "ORDER BY ordinal")).mappings().all()
            assert [c["column_name"] for c in cols] == ["id", "learner_email"]
            # the sensitive column carries stats but never values
            assert cols[1]["sensitivity"] == "sensitive"
            assert cols[1]["min_value"] is None

            sample = conn.execute(text("SELECT * FROM cat_samples")).mappings().one()
            assert json.loads(sample["sampled_columns"]) == ["id"]
            assert json.loads(sample["rows"]) == [{"id": "1"}, {"id": "2"}]
