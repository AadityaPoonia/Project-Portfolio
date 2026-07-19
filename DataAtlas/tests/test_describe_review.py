"""Phase 3 spec: description drafting is grounded, queued, and reviewable.

The LLM is a fake callable here — these tests pin the harness around it:
what it is shown, what tier/status drafts land with, and that refreshes
don't re-describe already-covered tables.
"""
import json

import pytest
from sqlalchemy import text

from datadict.describe import build_prompt, describe_run, tier_for
from datadict.sandbox import Sandbox
from datadict.schema_extract import Table, Column
from datadict.stats import ColumnStats


@pytest.fixture
def sandbox_with_run(tmp_path):
    sb = Sandbox(f"sqlite:///{tmp_path}/cat.db")
    run_id = sb.start_run("demo")
    t = Table(schema="public", name="threads", row_estimate=2396)
    t.columns = [Column("id", "bigint", False, 1, sensitivity="internal"),
                 Column("title", "varchar", True, 2, sensitivity="unknown"),
                 Column("user_email", "varchar", True, 3, sensitivity="sensitive")]
    t.primary_key = ["id"]
    stats = {"id": ColumnStats("id", null_frac=0.0, distinct_count=2396,
                               min_value="1", max_value="2396"),
             "title": ColumnStats("title", null_frac=0.1, distinct_count=2000),
             "user_email": ColumnStats("user_email", null_frac=0.0,
                                       distinct_count=900)}
    sb.write_table(run_id, "demo", t, stats, ["id"], [{"id": "1"}, {"id": "2"}])
    sb.finish_run(run_id, "success", 1)
    return sb, run_id


class TestPromptGrounding:
    def test_prompt_contains_stats_but_no_sensitive_values(self, sandbox_with_run):
        sb, run_id = sandbox_with_run
        table = sb.tables_for_run(run_id)[0]
        cols = sb.columns_for_run(run_id, "threads")
        prompt = build_prompt(table, cols, sb.samples_for_run(run_id, "threads"))
        payload = json.loads(prompt)
        assert payload["table"] == "public.threads"
        names = {c["name"] for c in payload["columns"]}
        assert names == {"id", "title", "user_email"}
        email_col = next(c for c in payload["columns"] if c["name"] == "user_email")
        # shape stats only — the sandbox holds no values for it, so neither can the prompt
        assert email_col["distinct_count"] == 900
        assert "min" not in email_col and "top_values" not in email_col
        assert payload["sample_rows"] == [{"id": "1"}, {"id": "2"}]

    def test_tiers(self):
        assert tier_for({"sensitivity": "internal"}) == "medium"
        assert tier_for({"sensitivity": "public"}) == "medium"
        assert tier_for({"sensitivity": "sensitive"}) == "flagged"
        assert tier_for({"sensitivity": "unknown"}) == "flagged"


class TestDescribeRun:
    @staticmethod
    def _fake_llm(system, user):
        cols = {c["name"]: f"desc of {c['name']}"
                for c in json.loads(user)["columns"]}
        return {"table_description": "Discussion threads.", "columns": cols}

    def test_drafts_land_pending_with_tiers(self, sandbox_with_run):
        sb, run_id = sandbox_with_run
        n = describe_run(sb, "demo", run_id, self._fake_llm, "fake-model")
        assert n == 1
        with sb.engine.connect() as conn:
            rows = [dict(r) for r in conn.execute(
                text("SELECT * FROM cat_descriptions ORDER BY id")).mappings()]
        assert len(rows) == 4                      # 1 table + 3 columns
        assert all(r["status"] == "pending" for r in rows)
        by_col = {r["column_name"]: r for r in rows}
        assert by_col[None]["description"] == "Discussion threads."
        assert by_col["id"]["tier"] == "medium"
        assert by_col["user_email"]["tier"] == "flagged"

    def test_refresh_skips_already_described(self, sandbox_with_run):
        sb, run_id = sandbox_with_run
        assert describe_run(sb, "demo", run_id, self._fake_llm, "fake-model") == 1
        # second pass: nothing to do, the LLM must not be called again
        def exploding_llm(system, user):
            raise AssertionError("LLM re-called for an already-described table")
        assert describe_run(sb, "demo", run_id, exploding_llm, "fake-model") == 0
        # unless forced
        assert describe_run(sb, "demo", run_id, self._fake_llm, "fake-model",
                            force=True) == 1


class TestApproveAll:
    def test_bulk_approve_skips_flagged_by_default(self, sandbox_with_run):
        sb, run_id = sandbox_with_run
        describe_run(sb, "demo", run_id, TestDescribeRun._fake_llm, "fake-model")
        from datadict.review import cmd_approve_all
        cmd_approve_all(sb, "descriptions", tier=None, table=None, note=None)
        with sb.engine.connect() as conn:
            rows = [dict(r) for r in conn.execute(
                text("SELECT tier, status FROM cat_descriptions")).mappings()]
        # medium tiers approved (table desc + id), flagged left pending
        assert {r["status"] for r in rows if r["tier"] == "medium"} == {"approved"}
        assert {r["status"] for r in rows if r["tier"] == "flagged"} == {"pending"}
        # explicit flagged pass approves the rest
        cmd_approve_all(sb, "descriptions", tier="flagged", table=None, note="ok")
        with sb.engine.connect() as conn:
            left = conn.execute(text(
                "SELECT COUNT(*) FROM cat_descriptions WHERE status='pending'")).scalar()
        assert left == 0


class TestReviewQueue:
    def test_approve_reject_and_edit(self, sandbox_with_run):
        sb, run_id = sandbox_with_run
        describe_run(sb, "demo", run_id, TestDescribeRun._fake_llm, "fake-model")
        assert sb.review_item("description", 1, "approved",
                              new_text="Human-corrected text.")
        assert sb.review_item("description", 2, "rejected", note="wrong")
        assert not sb.review_item("description", 999, "approved")
        with sb.engine.connect() as conn:
            r1 = conn.execute(text(
                "SELECT * FROM cat_descriptions WHERE id=1")).mappings().one()
            r2 = conn.execute(text(
                "SELECT * FROM cat_descriptions WHERE id=2")).mappings().one()
        assert r1["status"] == "approved"
        assert r1["description"] == "Human-corrected text."
        assert r1["reviewed_at"] is not None
        assert r2["status"] == "rejected" and r2["reviewer_note"] == "wrong"
