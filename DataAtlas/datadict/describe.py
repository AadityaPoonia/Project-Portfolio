"""Phase 3: LLM-drafted table & column descriptions.

    python -m datadict.describe [--config sources.yml] [--source NAME]
                                [--limit N] [--force] [--model MODEL]

Reads the latest successful extraction run from the SANDBOX (never the
source databases), asks the LLM for grounded plain-English descriptions,
and stores every draft as status='pending' in cat_descriptions. Nothing
is auto-published: per the design's confidence tiers, LLM prose is
'medium' at best, and sensitive/unknown columns are 'flagged'. Humans
approve via `python -m datadict.review`.
"""
import argparse
import json
import sys
from typing import Callable

from .config import load_config
from .sandbox import Sandbox

MAX_SAMPLE_ROWS_IN_PROMPT = 5
MAX_TOP_VALUES_IN_PROMPT = 8

_SYSTEM = """You are documenting a database for an internal data dictionary.
You will receive metadata for ONE table: its columns, types, statistics, and a few masked sample rows.
Sensitive columns have no values or min/max — describe them from name, type, and shape statistics only.

Rules:
- Ground every statement ONLY in the metadata provided. Do not invent business context.
- If a column's purpose is not evident, say what is observable (type, cardinality, null rate) rather than guessing.
- One to two sentences per description, plain English, present tense.

Return JSON exactly in this shape:
{"table_description": "...", "columns": {"<column_name>": "...", ...}}
Include EVERY column listed in the input."""


def _column_summary(col: dict) -> dict:
    """Serialize one cat_columns row for the prompt — sandbox data only,
    so sensitive/unknown columns already carry no raw values."""
    out = {
        "name": col["column_name"],
        "type": col["data_type"],
        "nullable": bool(col["is_nullable"]),
        "sensitivity": col["sensitivity"],
    }
    if col["null_frac"] is not None:
        out["null_frac"] = col["null_frac"]
    if col["distinct_count"] is not None:
        out["distinct_count"] = col["distinct_count"]
    if col["min_value"] is not None:
        out["min"] = col["min_value"]
    if col["max_value"] is not None:
        out["max"] = col["max_value"]
    if col["top_values"]:
        top = json.loads(col["top_values"])[:MAX_TOP_VALUES_IN_PROMPT]
        if top:   # stored as "[]" for value-less tiers — keep those out entirely
            out["top_values"] = top
    return out


def build_prompt(table: dict, columns: list[dict], sample: dict | None) -> str:
    payload = {
        "table": f'{table["table_schema"]}.{table["table_name"]}',
        "row_estimate": table["row_estimate"],
        "primary_key": json.loads(table["primary_key"] or "[]"),
        "foreign_keys": json.loads(table["foreign_keys"] or "[]"),
        "columns": [_column_summary(c) for c in columns],
    }
    if sample:
        payload["sample_rows"] = json.loads(sample["rows"])[:MAX_SAMPLE_ROWS_IN_PROMPT]
        payload["note"] = ("sample_rows contain only non-sensitive columns; "
                           "other columns exist but their values are withheld")
    return json.dumps(payload, indent=1)


def tier_for(col: dict) -> str:
    """Design section 8: sensitive/unknown columns are always 'flagged'
    (sign-off required even for masked descriptions); other LLM drafts
    are 'medium' — quick approve/edit."""
    return "flagged" if col["sensitivity"] in ("sensitive", "unknown") else "medium"


def describe_run(sandbox: Sandbox, source: str, run_id: str,
                 complete_json: Callable[[str, str], dict], model_name: str,
                 limit: int | None = None, force: bool = False,
                 only_table: str | None = None) -> int:
    tables = sandbox.tables_for_run(run_id)
    already = set() if force else sandbox.described_tables(source)
    n_done = 0
    for table in tables:
        tname = table["table_name"]
        if only_table and tname != only_table:
            continue
        if tname in already:
            continue
        if limit is not None and n_done >= limit:
            break
        columns = sandbox.columns_for_run(run_id, tname)
        sample = sandbox.samples_for_run(run_id, tname)

        result = complete_json(_SYSTEM, build_prompt(table, columns, sample))
        col_descriptions = result.get("columns") or {}

        sandbox.add_description(run_id, source, table["table_schema"], tname,
                                None, str(result.get("table_description", "")).strip(),
                                model_name, tier="medium")
        for col in columns:
            desc = str(col_descriptions.get(col["column_name"], "")).strip()
            if not desc:
                desc = "(model returned no description — needs manual entry)"
            sandbox.add_description(run_id, source, table["table_schema"], tname,
                                    col["column_name"], desc, model_name,
                                    tier=tier_for(col))
        n_done += 1
        print(f"  {tname}: drafted 1 table + {len(columns)} column descriptions")
    return n_done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM description drafting (Phase 3)")
    parser.add_argument("--config", default="sources.yml")
    parser.add_argument("--source", help="only this source name")
    parser.add_argument("--limit", type=int, help="describe at most N tables (per source)")
    parser.add_argument("--force", action="store_true",
                        help="re-describe tables that already have descriptions")
    parser.add_argument("--table", help="only this table (combine with --force to redo one)")
    parser.add_argument("--model", help="override OPENAI_MODEL")
    args = parser.parse_args(argv)

    from .llm import LLMClient  # constructed here so tests never need a key
    app = load_config(args.config)
    sandbox = Sandbox(app.sandbox_url)
    client = LLMClient(model=args.model)

    total = 0
    names = [s.name for s in app.sources if not args.source or s.name == args.source]
    if not names:
        print(f"no source named {args.source!r} in {args.config}", file=sys.stderr)
        return 1
    for name in names:
        run_id = sandbox.latest_run(name)
        if not run_id:
            print(f"[{name}] no successful extraction run yet — run "
                  f"datadict.run_extraction first", file=sys.stderr)
            continue
        print(f"[{name}] describing run {run_id} with {client.model}")
        total += describe_run(sandbox, name, run_id, client.complete_json,
                              client.model, args.limit, args.force, args.table)
    print(f"\ndrafted descriptions for {total} table(s); "
          f"review with: python -m datadict.review list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
