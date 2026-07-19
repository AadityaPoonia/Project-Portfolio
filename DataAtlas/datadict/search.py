"""Phase 5: the searchable catalog.

    python -m datadict.search find TERM            # tables/columns/descriptions
    python -m datadict.search show TABLE           # full detail for one table
    python -m datadict.search export [--out catalog.html]

Reads only the sandbox. Approved descriptions are shown as-is; pending
ones appear marked '(draft)' in the CLI and are EXCLUDED from the HTML
export — the published catalog contains reviewed content only.
"""
import argparse
import html
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from .config import load_config
from .sandbox import Sandbox, cat_descriptions, cat_relationships


def _latest_catalog(sandbox: Sandbox) -> tuple[list[dict], list[dict]]:
    """(tables, columns) across the latest successful run of every source."""
    tables, columns = [], []
    for source in sandbox.sources():
        rid = sandbox.latest_run(source)
        if rid:
            tables += sandbox.tables_for_run(rid)
            columns += sandbox.columns_for_run(rid)
    return tables, columns


def _descriptions(sandbox: Sandbox, statuses: tuple[str, ...]) -> dict[tuple, dict]:
    """{(source, schema, table, column|None): row} — newest row wins."""
    q = (select(cat_descriptions)
         .where(cat_descriptions.c.status.in_(statuses))
         .order_by(cat_descriptions.c.id))
    out: dict[tuple, dict] = {}
    with sandbox.engine.connect() as conn:
        for r in conn.execute(q).mappings():
            key = (r["source"], r["table_schema"], r["table_name"], r["column_name"])
            out[key] = dict(r)
    return out


def _relationships(sandbox: Sandbox, statuses: tuple[str, ...]) -> list[dict]:
    with sandbox.engine.connect() as conn:
        rows = conn.execute(
            select(cat_relationships)
            .where(cat_relationships.c.status.in_(statuses))
            .order_by(cat_relationships.c.id)
        ).mappings().all()
    # Runs append history, so the same relationship recurs across refreshes;
    # keep only the newest row per (kind, endpoints).
    latest: dict[tuple, dict] = {}
    for r in rows:
        key = (r["kind"], r["src_source"], r["src_schema"], r["src_table"],
               r["src_column"], r["dst_source"], r["dst_schema"],
               r["dst_table"], r["dst_column"])
        latest[key] = dict(r)
    return sorted(latest.values(), key=lambda r: (r["confidence"], r["id"]))


def _fmt_desc(d: dict | None) -> str:
    if not d:
        return ""
    suffix = " (draft)" if d["status"] == "pending" else ""
    return d["description"] + suffix


def cmd_find(sandbox: Sandbox, term: str) -> int:
    term_l = term.lower()
    tables, columns = _latest_catalog(sandbox)
    descs = _descriptions(sandbox, ("approved", "pending"))

    hits = 0
    for t in tables:
        key = (t["source"], t["table_schema"], t["table_name"], None)
        d = descs.get(key)
        text = f'{t["table_name"]} {_fmt_desc(d)}'.lower()
        if term_l in text:
            print(f'TABLE  {t["source"]}:{t["table_schema"]}.{t["table_name"]} '
                  f'(~{t["row_estimate"]} rows)')
            if d:
                print(f'       {_fmt_desc(d)}')
            hits += 1
    for c in columns:
        key = (c["source"], c["table_schema"], c["table_name"], c["column_name"])
        d = descs.get(key)
        text = f'{c["column_name"]} {_fmt_desc(d)}'.lower()
        if term_l in text:
            print(f'COLUMN {c["table_name"]}.{c["column_name"]} '
                  f'[{c["data_type"]}, {c["sensitivity"]}]')
            if d:
                print(f'       {_fmt_desc(d)}')
            hits += 1
    print(f"\n{hits} hit(s) for {term!r}")
    return 0


def cmd_show(sandbox: Sandbox, table_name: str) -> int:
    tables, columns = _latest_catalog(sandbox)
    matches = [t for t in tables if t["table_name"] == table_name]
    if not matches:
        print(f"no table named {table_name!r} in the catalog", file=sys.stderr)
        return 1
    descs = _descriptions(sandbox, ("approved", "pending"))
    rels = _relationships(sandbox, ("approved", "pending"))

    for t in matches:
        full = f'{t["source"]}:{t["table_schema"]}.{t["table_name"]}'
        print(f"\n=== {full} (~{t['row_estimate']} rows) ===")
        d = descs.get((t["source"], t["table_schema"], t["table_name"], None))
        if d:
            print(_fmt_desc(d))
        pk = json.loads(t["primary_key"] or "[]")
        if pk:
            print(f"primary key: {', '.join(pk)}")

        print()
        for c in columns:
            if (c["source"], c["table_schema"], c["table_name"]) != \
                    (t["source"], t["table_schema"], t["table_name"]):
                continue
            cd = descs.get((c["source"], c["table_schema"], c["table_name"],
                            c["column_name"]))
            stats_bits = []
            if c["null_frac"] is not None:
                stats_bits.append(f"null {c['null_frac']:.0%}")
            if c["distinct_count"] is not None:
                stats_bits.append(f"{c['distinct_count']} distinct")
            print(f'  {c["column_name"]:<32} {c["data_type"]:<20} '
                  f'{c["sensitivity"]:<10} {", ".join(stats_bits)}')
            if cd:
                print(f'      {_fmt_desc(cd)}')

        mine = [r for r in rels
                if table_name in (r["src_table"], r["dst_table"])]
        if mine:
            print("\n  relationships:")
            for r in mine:
                ov = "" if r["overlap_frac"] is None else f' ({r["overlap_frac"]:.0%} overlap)'
                flag = "" if r["status"] == "approved" else " [pending review]"
                print(f'    {r["src_table"]}.{r["src_column"]} -> '
                      f'{r["dst_table"]}.{r["dst_column"]} '
                      f'[{r["kind"]}, {r["confidence"]}]{ov}{flag}')
                if r["narration"]:
                    print(f'      {r["narration"]}')
    return 0


def cmd_export(sandbox: Sandbox, out_path: str) -> int:
    tables, columns = _latest_catalog(sandbox)
    descs = _descriptions(sandbox, ("approved",))          # published = reviewed only
    rels = _relationships(sandbox, ("approved",))
    e = html.escape

    parts = [
        "<meta charset='utf-8'><title>Data Dictionary</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;"
        "padding:0 1rem;color:#1a1a2e}h2{border-bottom:2px solid #ddd;padding-bottom:4px;"
        "margin-top:2.5rem}table{border-collapse:collapse;width:100%;font-size:14px}"
        "td,th{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}"
        "th{background:#f4f4f8}.sens-sensitive,.sens-unknown{color:#b3261e;font-weight:600}"
        ".sens-internal{color:#5b5b73}.sens-public{color:#1b6e3c}"
        ".muted{color:#777;font-size:12px}#q{width:100%;padding:8px;font-size:16px;"
        "margin:1rem 0;box-sizing:border-box}</style>",
        "<h1>Data Dictionary</h1>",
        f"<p class='muted'>generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — "
        "approved content only; drafts remain in the review queue</p>",
        "<input id='q' placeholder='filter tables and columns…' "
        "onkeyup='f(this.value.toLowerCase())'>",
        "<script>function f(v){document.querySelectorAll('section').forEach(s=>{"
        "s.style.display=s.textContent.toLowerCase().includes(v)?'':'none'})}</script>",
    ]

    for t in sorted(tables, key=lambda x: (x["source"], x["table_name"])):
        tkey = (t["source"], t["table_schema"], t["table_name"])
        d = descs.get((*tkey, None))
        parts.append("<section>")
        parts.append(f"<h2>{e(t['table_name'])} "
                     f"<span class='muted'>{e(t['source'])}:{e(t['table_schema'])}, "
                     f"~{t['row_estimate']} rows</span></h2>")
        if d:
            parts.append(f"<p>{e(d['description'])}</p>")
        parts.append("<table><tr><th>column</th><th>type</th><th>sensitivity</th>"
                     "<th>stats</th><th>description</th></tr>")
        for c in columns:
            if (c["source"], c["table_schema"], c["table_name"]) != tkey:
                continue
            cd = descs.get((*tkey, c["column_name"]))
            stats_bits = []
            if c["null_frac"] is not None:
                stats_bits.append(f"null {c['null_frac']:.0%}")
            if c["distinct_count"] is not None:
                stats_bits.append(f"{c['distinct_count']} distinct")
            parts.append(
                f"<tr><td>{e(c['column_name'])}</td><td>{e(c['data_type'] or '')}</td>"
                f"<td class='sens-{e(c['sensitivity'])}'>{e(c['sensitivity'])}</td>"
                f"<td>{e(', '.join(stats_bits))}</td>"
                f"<td>{e(cd['description']) if cd else ''}</td></tr>")
        parts.append("</table>")

        mine = [r for r in rels if t["table_name"] in (r["src_table"], r["dst_table"])]
        if mine:
            parts.append("<p><b>Relationships</b></p><ul>")
            for r in mine:
                ov = "" if r["overlap_frac"] is None else f" — {r['overlap_frac']:.0%} overlap"
                narr = f" {e(r['narration'])}" if r["narration"] else ""
                parts.append(
                    f"<li>{e(r['src_table'])}.{e(r['src_column'])} → "
                    f"{e(r['dst_table'])}.{e(r['dst_column'])} "
                    f"<span class='muted'>[{e(r['kind'])}, {e(r['confidence'])}{ov}]</span>"
                    f"{narr}</li>")
            parts.append("</ul>")
        parts.append("</section>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"wrote {out_path}: {len(tables)} tables, "
          f"{len(descs)} approved descriptions, {len(rels)} approved relationships")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Catalog search & export (Phase 5)")
    parser.add_argument("--config", default="sources.yml")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_find = sub.add_parser("find")
    p_find.add_argument("term")
    p_show = sub.add_parser("show")
    p_show.add_argument("table")
    p_exp = sub.add_parser("export")
    p_exp.add_argument("--out", default="catalog.html")

    args = parser.parse_args(argv)
    sandbox = Sandbox(load_config(args.config).sandbox_url)
    if args.cmd == "find":
        return cmd_find(sandbox, args.term)
    if args.cmd == "show":
        return cmd_show(sandbox, args.table)
    return cmd_export(sandbox, args.out)


if __name__ == "__main__":
    sys.exit(main())
