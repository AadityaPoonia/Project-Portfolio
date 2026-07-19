"""Row sampling — only columns whose tier allows raw values off the source.

The SELECT list is built from allowed columns only; sensitive/unknown
columns never appear in the query at all, so their values cannot leak
even if downstream code mishandles the result.
"""
from .classify import values_allowed
from .connections import GuardedSource
from .schema_extract import Table
from .stats import quote_ident

DEFAULT_SAMPLE_SIZE = 100


def sample_table(source: GuardedSource, table: Table,
                 sample_size: int = DEFAULT_SAMPLE_SIZE) -> tuple[list[str], list[dict]]:
    """Return (sampled_column_names, rows). Rows are JSON-safe dicts.

    Sampling is a plain LIMIT — cheap and predictable on all three engines.
    That biases samples toward storage order (often oldest rows); fine for
    "what does this data look like", not for statistics — stats.py computes
    those over the full table separately.
    """
    kind = source.engine_kind
    allowed = [c.name for c in table.columns if values_allowed(c.sensitivity)]
    if not allowed:
        return [], []

    select_list = ", ".join(quote_ident(c, kind) for c in allowed)
    tbl = f"{quote_ident(table.schema, kind)}.{quote_ident(table.name, kind)}"
    rows = source.fetch(f"SELECT {select_list} FROM {tbl} LIMIT {int(sample_size)}")

    safe_rows = [{k: (v if v is None else str(v)) for k, v in r.items()} for r in rows]
    return allowed, safe_rows
