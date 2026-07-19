"""Phase 5: change tracking between extraction runs.

    python -m datadict.changes [--config sources.yml] [--source NAME]

Diffs the two most recent successful runs of each source: new/dropped
tables, added/removed columns, type changes, and sensitivity changes
(a column flipping to 'sensitive' after a PII-scan escalation shows up
here). Pure read of the sandbox; exits 0 always so cron mail stays quiet.
"""
import argparse
import sys
from dataclasses import dataclass, field

from .config import load_config
from .sandbox import Sandbox


@dataclass
class RunDiff:
    source: str
    old_run: str
    new_run: str
    new_tables: list[str] = field(default_factory=list)
    dropped_tables: list[str] = field(default_factory=list)
    added_columns: list[str] = field(default_factory=list)      # "table.column"
    removed_columns: list[str] = field(default_factory=list)
    type_changes: list[str] = field(default_factory=list)       # "table.column: a -> b"
    sensitivity_changes: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any((self.new_tables, self.dropped_tables, self.added_columns,
                        self.removed_columns, self.type_changes,
                        self.sensitivity_changes))


def diff_runs(sandbox: Sandbox, source: str, old_run: str, new_run: str) -> RunDiff:
    d = RunDiff(source=source, old_run=old_run, new_run=new_run)

    old_tables = {t["table_name"] for t in sandbox.tables_for_run(old_run)}
    new_tables = {t["table_name"] for t in sandbox.tables_for_run(new_run)}
    d.new_tables = sorted(new_tables - old_tables)
    d.dropped_tables = sorted(old_tables - new_tables)

    def col_map(run_id):
        return {(c["table_name"], c["column_name"]): c
                for c in sandbox.columns_for_run(run_id)}

    old_cols, new_cols = col_map(old_run), col_map(new_run)
    common_tables = old_tables & new_tables
    for key in sorted(new_cols.keys() - old_cols.keys()):
        if key[0] in common_tables:
            d.added_columns.append(f"{key[0]}.{key[1]}")
    for key in sorted(old_cols.keys() - new_cols.keys()):
        if key[0] in common_tables:
            d.removed_columns.append(f"{key[0]}.{key[1]}")
    for key in sorted(old_cols.keys() & new_cols.keys()):
        o, n = old_cols[key], new_cols[key]
        if o["data_type"] != n["data_type"]:
            d.type_changes.append(
                f"{key[0]}.{key[1]}: {o['data_type']} -> {n['data_type']}")
        if o["sensitivity"] != n["sensitivity"]:
            d.sensitivity_changes.append(
                f"{key[0]}.{key[1]}: {o['sensitivity']} -> {n['sensitivity']}")
    return d


def print_diff(d: RunDiff) -> None:
    print(f"[{d.source}] {d.old_run[:8]} -> {d.new_run[:8]}")
    if d.is_empty():
        print("  no changes")
        return
    for label, items in [("new tables", d.new_tables),
                         ("dropped tables", d.dropped_tables),
                         ("added columns", d.added_columns),
                         ("removed columns", d.removed_columns),
                         ("type changes", d.type_changes),
                         ("sensitivity changes", d.sensitivity_changes)]:
        for item in items:
            print(f"  {label}: {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run-over-run change tracking (Phase 5)")
    parser.add_argument("--config", default="sources.yml")
    parser.add_argument("--source", help="only this source name")
    args = parser.parse_args(argv)

    sandbox = Sandbox(load_config(args.config).sandbox_url)
    sources = [args.source] if args.source else sandbox.sources()
    for source in sources:
        history = sandbox.run_history(source)
        if len(history) < 2:
            print(f"[{source}] fewer than two successful runs — nothing to diff")
            continue
        print_diff(diff_runs(sandbox, source, history[1], history[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
