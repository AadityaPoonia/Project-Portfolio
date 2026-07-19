"""Phase 4 spec: deterministic candidate generation + validation.

The design contract under test: no relationship is stored without a
deterministic name/type match AND a measured value overlap; validation
queries return counts only.
"""
import json

import pytest
from sqlalchemy import text

from datadict.audit import AuditLog
from datadict.connections import GuardedSource
from datadict.relationships import (
    Candidate, ColRef, confidence_for, generate_candidates,
    sample_overlap, validate_same_source,
)
from datadict.sandbox import Sandbox
from datadict.schema_extract import Table, Column
from datadict.stats import ColumnStats


def _table_row(source, table, pk=("id",), fks=(), rows=100):
    return {"source": source, "table_schema": "public", "table_name": table,
            "row_estimate": rows, "primary_key": json.dumps(list(pk)),
            "foreign_keys": json.dumps(list(fks))}


def _col_row(source, table, column, dtype="bigint", distinct=None):
    return {"source": source, "table_schema": "public", "table_name": table,
            "column_name": column, "data_type": dtype, "distinct_count": distinct}


class TestCandidateGeneration:
    def test_entity_id_matches_plural_table_pk(self):
        tables = [_table_row("s", "users"), _table_row("s", "threads")]
        columns = [_col_row("s", "users", "id"),
                   _col_row("s", "threads", "id"),
                   _col_row("s", "threads", "user_id")]
        cands = generate_candidates(tables, columns)
        assert any(c.src.column == "user_id" and c.dst.table == "users"
                   and c.dst.column == "id" for c in cands)

    def test_generic_id_columns_do_not_pair_with_each_other(self):
        tables = [_table_row("s", "users"), _table_row("s", "threads")]
        columns = [_col_row("s", "users", "id"), _col_row("s", "threads", "id")]
        cands = generate_candidates(tables, columns)
        assert cands == []

    def test_declared_fk_is_not_recandidated(self):
        fk = {"column": "user_id", "ref_schema": "public",
              "ref_table": "users", "ref_column": "id", "enforced": True}
        tables = [_table_row("s", "users"), _table_row("s", "threads", fks=[fk])]
        columns = [_col_row("s", "users", "id"),
                   _col_row("s", "threads", "user_id")]
        assert generate_candidates(tables, columns) == []

    def test_type_mismatch_rejected(self):
        tables = [_table_row("s", "users"), _table_row("s", "threads")]
        columns = [_col_row("s", "users", "id", dtype="varchar"),
                   _col_row("s", "threads", "user_id", dtype="bigint")]
        assert generate_candidates(tables, columns) == []

    def test_same_name_needs_unique_destination(self):
        tables = [_table_row("s", "a", pk=(), rows=100),
                  _table_row("s", "b", pk=(), rows=100)]
        # neither side unique (low distinct/row ratio) -> no destination -> no pair
        columns = [_col_row("s", "a", "external_ref", distinct=50),
                   _col_row("s", "b", "external_ref", distinct=5)]
        assert generate_candidates(tables, columns) == []
        # b side becomes unique -> exactly one candidate, a -> b
        columns[1]["distinct_count"] = 98
        cands = generate_candidates(tables, columns)
        assert len(cands) == 1 and cands[0].reason == "same_name"
        assert cands[0].src.table == "a" and cands[0].dst.table == "b"


class TestConfidence:
    @pytest.mark.parametrize("overlap,method,reason,expected", [
        (1.0, "join_overlap", "name_convention", "high"),
        (0.995, "join_overlap", "name_convention", "high"),
        (0.95, "join_overlap", "name_convention", "medium"),
        (1.0, "join_overlap", "same_name", "medium"),   # no naming convention -> never high
        (0.6, "join_overlap", "name_convention", "low"),
        (1.0, "sample_overlap", "name_convention", "low"),  # samples cap at low
    ])
    def test_tiers(self, overlap, method, reason, expected):
        assert confidence_for(overlap, method, reason) == expected


class TestValidation:
    @pytest.fixture
    def guarded(self, tmp_path, monkeypatch):
        monkeypatch.setattr("datadict.connections._connect_args", lambda *a: {})
        src = GuardedSource("demo", "mysql", f"sqlite:///{tmp_path}/src.db",
                            AuditLog(str(tmp_path / "audit.jsonl")))
        with src._engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE threads (id INTEGER, user_id INTEGER)"))
            for i in range(50):
                conn.execute(text("INSERT INTO users VALUES (:i)"), {"i": i})
            for i in range(80):
                # user_ids 0..79: 50..79 dangle -> 5/8 of distinct values match
                conn.execute(text("INSERT INTO threads VALUES (:i, :u)"),
                             {"i": i, "u": i})
        yield src
        src.dispose()

    def test_overlap_is_measured_not_assumed(self, guarded):
        cand = Candidate(ColRef("demo", "main", "threads", "user_id"),
                         ColRef("demo", "main", "users", "id"),
                         "name_convention")
        overlap, n = validate_same_source(guarded, cand)
        assert n == 80
        assert overlap == pytest.approx(50 / 80)

    def test_validation_query_returns_counts_only(self, guarded, tmp_path):
        cand = Candidate(ColRef("demo", "main", "threads", "user_id"),
                         ColRef("demo", "main", "users", "id"),
                         "name_convention")
        validate_same_source(guarded, cand)
        events = (tmp_path / "audit.jsonl").read_text().splitlines()
        last = json.loads(events[-1])
        assert last["status"] == "allowed"
        assert last["rows"] == 1          # one aggregate row, never raw values


class TestSampleOverlap:
    def test_cross_source_uses_sandbox_samples(self, tmp_path):
        sb = Sandbox(f"sqlite:///{tmp_path}/cat.db")
        run_a, run_b = sb.start_run("src_a"), sb.start_run("src_b")

        ta = Table(schema="public", name="orders", row_estimate=3)
        ta.columns = [Column("course_code", "varchar", False, 1, sensitivity="public")]
        sb.write_table(run_a, "src_a", ta,
                       {"course_code": ColumnStats("course_code")},
                       ["course_code"],
                       [{"course_code": "C1"}, {"course_code": "C2"},
                        {"course_code": "C9"}])
        tb = Table(schema="public", name="courses", row_estimate=2)
        tb.columns = [Column("course_code", "varchar", False, 1, sensitivity="public")]
        sb.write_table(run_b, "src_b", tb,
                       {"course_code": ColumnStats("course_code")},
                       ["course_code"],
                       [{"course_code": "C1"}, {"course_code": "C2"}])

        cand = Candidate(ColRef("src_a", "public", "orders", "course_code"),
                         ColRef("src_b", "public", "courses", "course_code"),
                         "same_name")
        result = sample_overlap(sb, {"src_a": run_a, "src_b": run_b}, cand)
        assert result is not None
        overlap, n = result
        assert n == 3 and overlap == pytest.approx(2 / 3)

    def test_unsampled_sensitive_column_returns_none(self, tmp_path):
        sb = Sandbox(f"sqlite:///{tmp_path}/cat2.db")
        run_a = sb.start_run("src_a")
        ta = Table(schema="public", name="orders", row_estimate=1)
        ta.columns = [Column("email", "varchar", False, 1, sensitivity="sensitive")]
        sb.write_table(run_a, "src_a", ta, {"email": ColumnStats("email")}, [], [])
        cand = Candidate(ColRef("src_a", "public", "orders", "email"),
                         ColRef("src_b", "public", "users", "email"),
                         "same_name")
        assert sample_overlap(sb, {"src_a": run_a, "src_b": run_a}, cand) is None
