"""Sensitivity-aware column statistics.

The allowed-stats list is explicit and CLOSED per tier:

- every column (any tier):   null %, distinct count
- public/internal only:      min/max (numeric, date/time only), top-k frequent
                             values (never for free-text types)

MIN/MAX and top-k ARE raw values, so they are never computed for
sensitive/unknown columns, and never for free-text columns of any tier
(free text can hide PII regardless of what the column is called).
"""
from dataclasses import dataclass, field

from .classify import values_allowed
from .connections import GuardedSource
from .schema_extract import Table, Column

_NUMERIC_TYPES = {
    "int", "integer", "bigint", "smallint", "tinyint", "mediumint",
    "decimal", "numeric", "float", "double", "real", "double precision",
}
_TEMPORAL_TYPES = {"date", "datetime", "timestamp", "time",
                   "timestamp without time zone", "timestamp with time zone"}
_FREE_TEXT_TYPES = {"text", "mediumtext", "longtext", "tinytext", "json", "jsonb", "blob"}

TOP_K = 10
TOP_K_MAX_CARDINALITY = 1000  # top-k only for enum-like columns
# Skip full-scan stats above this size; extraction must stay cheap.
MAX_ROWS_FOR_FULL_STATS = 20_000_000


@dataclass
class ColumnStats:
    column: str
    null_frac: float | None = None
    distinct_count: int | None = None
    min_value: str | None = None
    max_value: str | None = None
    top_values: list[dict] = field(default_factory=list)  # [{value, count}]
    skipped_reason: str | None = None


def quote_ident(name: str, engine_kind: str) -> str:
    if engine_kind == "mysql":
        return "`" + name.replace("`", "``") + "`"
    return '"' + name.replace('"', '""') + '"'


def _distinct_expr(col: str, engine_kind: str) -> str:
    if engine_kind == "redshift":
        return f"APPROXIMATE COUNT(DISTINCT {col})"
    return f"COUNT(DISTINCT {col})"


def collect_stats(source: GuardedSource, table: Table, column: Column) -> ColumnStats:
    stats = ColumnStats(column=column.name)

    if table.row_estimate is not None and table.row_estimate > MAX_ROWS_FOR_FULL_STATS:
        stats.skipped_reason = f"table too large ({table.row_estimate} rows)"
        return stats

    kind = source.engine_kind
    col = quote_ident(column.name, kind)
    tbl = f"{quote_ident(table.schema, kind)}.{quote_ident(table.name, kind)}"
    base_type = column.data_type.lower()

    rows = source.fetch(
        f"SELECT COUNT(*) AS n, COUNT({col}) AS non_null, "
        f"{_distinct_expr(col, kind)} AS n_distinct FROM {tbl}"
    )
    n = int(rows[0]["n"] or 0)
    if n:
        stats.null_frac = round(1 - int(rows[0]["non_null"]) / n, 4)
    stats.distinct_count = int(rows[0]["n_distinct"] or 0)

    if not values_allowed(column.sensitivity):
        return stats
    if base_type in _FREE_TEXT_TYPES:
        return stats

    if base_type in _NUMERIC_TYPES or base_type in _TEMPORAL_TYPES:
        rows = source.fetch(f"SELECT MIN({col}) AS mn, MAX({col}) AS mx FROM {tbl}")
        stats.min_value = str(rows[0]["mn"]) if rows[0]["mn"] is not None else None
        stats.max_value = str(rows[0]["mx"]) if rows[0]["mx"] is not None else None

    if stats.distinct_count and stats.distinct_count <= TOP_K_MAX_CARDINALITY:
        rows = source.fetch(
            f"SELECT {col} AS v, COUNT(*) AS c FROM {tbl} "
            f"WHERE {col} IS NOT NULL GROUP BY {col} "
            f"ORDER BY c DESC LIMIT {TOP_K}"
        )
        stats.top_values = [{"value": str(r["v"]), "count": int(r["c"])} for r in rows]

    return stats
