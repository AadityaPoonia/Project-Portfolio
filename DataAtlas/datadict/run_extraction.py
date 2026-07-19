"""Extraction job entry point.

    python -m datadict.run_extraction --config sources.yml [--source NAME] [--dry-run]

For each configured source: extract schema -> classify columns -> collect
stats -> sample allowed columns -> write everything to the sandbox catalog.
--dry-run stops after schema+classification and prints what would happen,
without collecting stats, sampling, or writing to the sandbox.
"""
import argparse
import sys

from .audit import AuditLog
from .classify import classify, values_allowed
from .config import load_config, SourceConfig
from .connections import GuardedSource, build_url
from .pii_scan import scan_samples
from .sampling import sample_table
from .sandbox import Sandbox
from .schema_extract import extract_schema
from .stats import collect_stats


def process_source(cfg: SourceConfig, sandbox: Sandbox | None,
                   audit: AuditLog, dry_run: bool) -> int:
    creds = cfg.credentials()
    url = build_url(cfg.engine, creds["user"], creds["password"],
                    creds["host"], creds["port"], creds["database"])

    run_id = sandbox.start_run(cfg.name) if sandbox else None
    source = GuardedSource(cfg.name, cfg.engine, url, audit,
                           row_cap=cfg.row_cap, timeout_s=cfg.timeout_s,
                           run_id=run_id)
    n_tables = 0
    try:
        for schema in cfg.schemas:
            allow = cfg.table_allowlist.get(schema)
            allowset = set(allow) if allow is not None else None
            tables = extract_schema(source, schema, allowset)
            print(f"[{cfg.name}] schema {schema!r}: {len(tables)} tables in scope")

            for table in tables:
                for col in table.columns:
                    col.sensitivity = classify(col.name, cfg.column_overrides)
                n_sampleable = sum(values_allowed(c.sensitivity) for c in table.columns)

                if dry_run:
                    print(f"  {schema}.{table.name}: {len(table.columns)} columns, "
                          f"{n_sampleable} sampleable, ~{table.row_estimate} rows")
                    n_tables += 1
                    continue

                # Sample first, then PII-scan the sample IN MEMORY. Escalated
                # columns lose their values here — before stats (so no min/max/
                # top-k is ever computed for them) and before any sandbox write.
                sampled_cols, sample_rows = sample_table(source, table, cfg.sample_size)
                findings = scan_samples(
                    [c for c in sampled_cols if c.lower() not in cfg.column_overrides],
                    sample_rows)  # human overrides are deliberate; don't second-guess
                for col in table.columns:
                    f = findings.get(col.name)
                    if f:
                        col.sensitivity = "sensitive"
                        print(f"  {schema}.{table.name}.{col.name}: escalated to "
                              f"sensitive (pii_scan: {f.detector}, "
                              f"{f.match_frac:.0%} of {f.n_checked} sampled values)")
                sampled_cols = [c for c in sampled_cols if c not in findings]
                sample_rows = [{k: v for k, v in r.items() if k not in findings}
                               for r in sample_rows] if sampled_cols else []

                col_stats = {c.name: collect_stats(source, table, c) for c in table.columns}
                for name, f in findings.items():
                    if name in col_stats:
                        col_stats[name].skipped_reason = (
                            f"pii_scan:{f.detector} ({f.match_frac:.0%} of sample)")
                sandbox.write_table(run_id, cfg.name, table, col_stats,
                                    sampled_cols, sample_rows)
                n_tables += 1
                print(f"  {schema}.{table.name}: done "
                      f"({len(table.columns)} cols, {len(sample_rows)} sample rows)")

        if sandbox:
            sandbox.finish_run(run_id, "success", n_tables)
    except Exception as e:
        if sandbox:
            sandbox.finish_run(run_id, "failed", n_tables, error=f"{type(e).__name__}: {e}")
        raise
    finally:
        source.dispose()
    return n_tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Data dictionary extraction job")
    parser.add_argument("--config", default="sources.yml")
    parser.add_argument("--source", help="only process this source name")
    parser.add_argument("--dry-run", action="store_true",
                        help="schema + classification only; no stats, samples, or sandbox writes")
    args = parser.parse_args(argv)

    app = load_config(args.config)
    audit = AuditLog(app.audit_log_path)
    sandbox = None if args.dry_run else Sandbox(app.sandbox_url)

    targets = [s for s in app.sources if not args.source or s.name == args.source]
    if not targets:
        print(f"no source named {args.source!r} in {args.config}", file=sys.stderr)
        return 1

    total = 0
    for cfg in targets:
        total += process_source(cfg, sandbox, audit, args.dry_run)
    print(f"\n{'would extract' if args.dry_run else 'extracted'} {total} tables "
          f"from {len(targets)} source(s); audit log: {app.audit_log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
