"""Phase 5 spec: change tracking between extraction runs."""
import pytest

from datadict.changes import diff_runs
from datadict.sandbox import Sandbox
from datadict.schema_extract import Table, Column
from datadict.stats import ColumnStats


def _write(sb, run_id, name, columns):
    t = Table(schema="public", name=name, row_estimate=10)
    t.columns = columns
    sb.write_table(run_id, "demo", t,
                   {c.name: ColumnStats(c.name) for c in columns}, [], [])


@pytest.fixture
def two_runs(tmp_path):
    sb = Sandbox(f"sqlite:///{tmp_path}/cat.db")

    old = sb.start_run("demo")
    _write(sb, old, "users", [Column("id", "bigint", False, 1, sensitivity="internal"),
                              Column("bio", "text", True, 2, sensitivity="unknown")])
    _write(sb, old, "legacy", [Column("id", "bigint", False, 1)])
    sb.finish_run(old, "success", 2)

    new = sb.start_run("demo")
    _write(sb, new, "users", [Column("id", "uuid", False, 1, sensitivity="internal"),
                              Column("bio", "text", True, 2, sensitivity="sensitive"),
                              Column("locale", "varchar", True, 3)])
    _write(sb, new, "threads", [Column("id", "bigint", False, 1)])
    sb.finish_run(new, "success", 2)
    return sb, old, new


def test_diff_catches_every_change_kind(two_runs):
    sb, old, new = two_runs
    d = diff_runs(sb, "demo", old, new)
    assert d.new_tables == ["threads"]
    assert d.dropped_tables == ["legacy"]
    assert d.added_columns == ["users.locale"]
    assert d.removed_columns == []
    assert d.type_changes == ["users.id: bigint -> uuid"]
    assert d.sensitivity_changes == ["users.bio: unknown -> sensitive"]
    assert not d.is_empty()


def test_identical_runs_diff_empty(tmp_path):
    sb = Sandbox(f"sqlite:///{tmp_path}/cat.db")
    runs = []
    for _ in range(2):
        rid = sb.start_run("demo")
        _write(sb, rid, "users", [Column("id", "bigint", False, 1)])
        sb.finish_run(rid, "success", 1)
        runs.append(rid)
    assert diff_runs(sb, "demo", runs[0], runs[1]).is_empty()


def test_run_history_orders_newest_first(two_runs):
    sb, old, new = two_runs
    assert sb.run_history("demo") == [new, old]
