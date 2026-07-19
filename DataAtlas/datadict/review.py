"""Phase 3/4 review queue CLI — the human side of the confidence tiers.

    python -m datadict.review list [--what descriptions|relationships] [--status pending] [--tier flagged]
    python -m datadict.review show ID [--what ...]
    python -m datadict.review approve ID [--what ...] [--edit "corrected text"] [--note "..."]
    python -m datadict.review reject  ID [--what ...] [--note "..."]
    python -m datadict.review approve-all [--what ...] [--tier medium] [--table threads] [--note "..."]

Only 'approved' items are surfaced by search/export. 'flagged' tier
(sensitive/unknown columns) always needs explicit sign-off: approve-all
skips flagged descriptions unless you pass --tier flagged on purpose.
"""
import argparse
import sys
import textwrap
from datetime import datetime, timezone

from sqlalchemy import select, or_

from .config import load_config
from .sandbox import Sandbox, cat_descriptions, cat_relationships


def _table_for(what: str):
    return cat_descriptions if what == "descriptions" else cat_relationships


def _entity(row: dict, what: str) -> str:
    if what == "descriptions":
        col = row["column_name"]
        return f'{row["table_name"]}.{col}' if col else f'{row["table_name"]} (table)'
    return (f'{row["src_table"]}.{row["src_column"]} -> '
            f'{row["dst_table"]}.{row["dst_column"]}')


def cmd_list(sandbox: Sandbox, what: str, status: str, tier: str | None) -> int:
    tbl = _table_for(what)
    q = select(tbl).where(tbl.c.status == status).order_by(tbl.c.id)
    if tier and what == "descriptions":
        q = q.where(tbl.c.tier == tier)
    with sandbox.engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(q).mappings().all()]
    if not rows:
        print(f"no {status} {what}")
        return 0
    for r in rows:
        if what == "descriptions":
            body = r["description"]
            prefix = r["tier"] + " | "
        else:
            ov = "-" if r["overlap_frac"] is None else f'{r["overlap_frac"]:.0%}'
            body = (f'{r["kind"]}/{r["method"]}, overlap {ov} of '
                    f'{r["n_checked"] or "?"} values, confidence {r["confidence"]}')
            if r["narration"]:
                body += f' — {r["narration"]}'
            prefix = r["confidence"] + " | "
        print(f'[{r["id"]:>4}] {prefix}{_entity(r, what)}')
        print(textwrap.indent(textwrap.fill(str(body), 96), "       "))
    print(f"\n{len(rows)} {status} {what}")
    return 0


def cmd_show(sandbox: Sandbox, what: str, item_id: int) -> int:
    tbl = _table_for(what)
    with sandbox.engine.connect() as conn:
        row = conn.execute(select(tbl).where(tbl.c.id == item_id)).mappings().first()
    if not row:
        print(f"no {what[:-1]} with id {item_id}", file=sys.stderr)
        return 1
    for k, v in dict(row).items():
        print(f"{k:>16}: {v}")
    return 0


def cmd_review(sandbox: Sandbox, what: str, item_id: int, status: str,
               note: str | None, edit: str | None) -> int:
    ok = sandbox.review_item(what[:-1], item_id, status, note=note, new_text=edit)
    if not ok:
        print(f"no {what[:-1]} with id {item_id}", file=sys.stderr)
        return 1
    print(f"{what[:-1]} {item_id}: {status}" + (" (edited)" if edit else ""))
    return 0


def cmd_approve_all(sandbox: Sandbox, what: str, tier: str | None,
                    table: str | None, note: str | None) -> int:
    tbl = _table_for(what)
    q = tbl.update().where(tbl.c.status == "pending")
    if what == "descriptions":
        # flagged = sensitive/unknown columns: sign-off must be deliberate
        q = q.where(tbl.c.tier == tier) if tier else q.where(tbl.c.tier != "flagged")
        if table:
            q = q.where(tbl.c.table_name == table)
    else:
        if tier:
            q = q.where(tbl.c.confidence == tier)
        if table:
            q = q.where(or_(tbl.c.src_table == table, tbl.c.dst_table == table))
    values = {"status": "approved", "reviewed_at": datetime.now(timezone.utc)}
    if note:
        values["reviewer_note"] = note
    with sandbox.engine.begin() as conn:
        res = conn.execute(q.values(**values))
    scope = " ".join(filter(None, [f"tier={tier}" if tier else "(flagged excluded)",
                                   f"table={table}" if table else None]))
    print(f"approved {res.rowcount} {what} {scope}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review queue (Phases 3-4)")
    parser.add_argument("--config", default="sources.yml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--what", choices=["descriptions", "relationships"],
                        default="descriptions")
    p_list.add_argument("--status", default="pending",
                        choices=["pending", "approved", "rejected"])
    p_list.add_argument("--tier", choices=["high", "medium", "low", "flagged"])

    p_show = sub.add_parser("show")
    p_show.add_argument("id", type=int)
    p_show.add_argument("--what", choices=["descriptions", "relationships"],
                        default="descriptions")

    for name in ("approve", "reject"):
        p = sub.add_parser(name)
        p.add_argument("id", type=int)
        p.add_argument("--what", choices=["descriptions", "relationships"],
                       default="descriptions")
        p.add_argument("--note")
        if name == "approve":
            p.add_argument("--edit", help="replace the description text while approving")

    p_all = sub.add_parser("approve-all")
    p_all.add_argument("--what", choices=["descriptions", "relationships"],
                       default="descriptions")
    p_all.add_argument("--tier", choices=["high", "medium", "low", "flagged"],
                       help="descriptions: tier to approve (default: all except flagged); "
                            "relationships: confidence level")
    p_all.add_argument("--table", help="only entries for this table")
    p_all.add_argument("--note")

    args = parser.parse_args(argv)
    sandbox = Sandbox(load_config(args.config).sandbox_url)

    if args.cmd == "list":
        return cmd_list(sandbox, args.what, args.status, args.tier)
    if args.cmd == "approve-all":
        return cmd_approve_all(sandbox, args.what, args.tier, args.table, args.note)
    if args.cmd == "show":
        return cmd_show(sandbox, args.what, args.id)
    status = "approved" if args.cmd == "approve" else "rejected"
    return cmd_review(sandbox, args.what, args.id, status,
                      args.note, getattr(args, "edit", None))


if __name__ == "__main__":
    sys.exit(main())
