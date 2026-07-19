"""Per-engine schema extraction.

Pulls tables, columns, types, nullability, declared keys, and row-count
estimates. Uses the right catalog per engine:

- MySQL:    information_schema (row counts are InnoDB *estimates*)
- Postgres: information_schema + pg_class.reltuples for row estimates
- Redshift: SVV_TABLE_INFO for tables (information_schema is slow/incomplete
            there); columns still come from information_schema, which is fine
            for column metadata. Declared FKs on Redshift are NOT enforced by
            the engine — they are recorded with enforced=False so downstream
            relationship validation still checks them against real data.

All queries run through GuardedSource.fetch(), so they are AST-validated,
row-capped, and audited like everything else.
"""
from dataclasses import dataclass, field

from .connections import GuardedSource


@dataclass
class Column:
    name: str
    data_type: str
    is_nullable: bool
    ordinal: int
    default: str | None = None
    sensitivity: str = "unknown"  # set later by the classifier


@dataclass
class ForeignKey:
    column: str
    ref_schema: str
    ref_table: str
    ref_column: str
    enforced: bool = True


@dataclass
class Table:
    schema: str
    name: str
    row_estimate: int | None
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)


_TABLES_SQL = {
    "mysql": """
        SELECT table_schema, table_name, table_rows AS row_estimate
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE' AND table_schema = :schema
    """,
    "postgres": """
        SELECT n.nspname AS table_schema, c.relname AS table_name,
               c.reltuples::bigint AS row_estimate
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r' AND n.nspname = :schema
    """,
    "redshift": """
        SELECT "schema" AS table_schema, "table" AS table_name,
               tbl_rows AS row_estimate
        FROM svv_table_info
        WHERE "schema" = :schema
    """,
}

# information_schema.columns works across all three engines
_COLUMNS_SQL = """
    SELECT table_name, column_name, data_type, is_nullable,
           ordinal_position, column_default
    FROM information_schema.columns
    WHERE table_schema = :schema
    ORDER BY table_name, ordinal_position
"""

_KEYS_SQL = {
    "mysql": """
        SELECT k.table_name, k.column_name, k.constraint_name,
               t.constraint_type,
               k.referenced_table_schema AS ref_schema,
               k.referenced_table_name   AS ref_table,
               k.referenced_column_name  AS ref_column
        FROM information_schema.key_column_usage k
        JOIN information_schema.table_constraints t
          ON  t.constraint_name  = k.constraint_name
          AND t.table_schema     = k.table_schema
          AND t.table_name       = k.table_name
        WHERE k.table_schema = :schema
          AND t.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
    """,
    # Redshift only. On real Postgres this view family is permission-filtered
    # (constraint_column_usage shows only tables the user OWNS), so a read-only
    # role silently gets zero keys — use the pg_catalog queries below instead.
    "postgres_family": """
        SELECT tc.table_name, kcu.column_name, tc.constraint_name,
               tc.constraint_type,
               ccu.table_schema AS ref_schema,
               ccu.table_name   AS ref_table,
               ccu.column_name  AS ref_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema    = tc.table_schema
        LEFT JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND tc.constraint_type  = 'FOREIGN KEY'
        WHERE tc.table_schema = :schema
          AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
    """,
}

# Postgres: pg_catalog is readable by any role with SELECT on the table,
# unlike information_schema's owner-filtered constraint views.
_PG_PK_SQL = """
    SELECT t.relname AS table_name, a.attname AS column_name,
           'PRIMARY KEY' AS constraint_type,
           NULL AS ref_schema, NULL AS ref_table, NULL AS ref_column
    FROM pg_index i
    JOIN pg_class t ON t.oid = i.indrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(i.indkey)
    WHERE i.indisprimary AND n.nspname = :schema
"""

# Single-column FKs only (conkey[1]); multi-column FKs are rare in these
# schemas and would need unnest-with-ordinality, which complicates the guard.
_PG_FK_SQL = """
    SELECT t.relname AS table_name, sa.attname AS column_name,
           'FOREIGN KEY' AS constraint_type,
           rn.nspname AS ref_schema, rt.relname AS ref_table,
           ra.attname AS ref_column
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN pg_class rt ON rt.oid = c.confrelid
    JOIN pg_namespace rn ON rn.oid = rt.relnamespace
    JOIN pg_attribute sa ON sa.attrelid = t.oid AND sa.attnum = c.conkey[1]
    JOIN pg_attribute ra ON ra.attrelid = rt.oid AND ra.attnum = c.confkey[1]
    WHERE c.contype = 'f' AND n.nspname = :schema
      AND array_length(c.conkey, 1) = 1
"""


def extract_schema(source: GuardedSource, schema: str,
                   table_allowlist: set[str] | None = None) -> list[Table]:
    """Extract all in-scope tables from one schema of one source."""
    kind = source.engine_kind

    tables: dict[str, Table] = {}
    for row in source.fetch(_TABLES_SQL[kind], {"schema": schema}):
        name = row["table_name"]
        if table_allowlist is not None and name not in table_allowlist:
            continue
        est = row["row_estimate"]
        tables[name] = Table(schema=schema, name=name,
                             row_estimate=int(est) if est is not None else None)

    for row in source.fetch(_COLUMNS_SQL, {"schema": schema}):
        t = tables.get(row["table_name"])
        if t is None:
            continue
        t.columns.append(Column(
            name=row["column_name"],
            data_type=row["data_type"],
            is_nullable=str(row["is_nullable"]).upper() == "YES",
            ordinal=int(row["ordinal_position"]),
            default=row["column_default"],
        ))

    if kind == "postgres":
        key_rows = (source.fetch(_PG_PK_SQL, {"schema": schema})
                    + source.fetch(_PG_FK_SQL, {"schema": schema}))
    elif kind == "mysql":
        key_rows = source.fetch(_KEYS_SQL["mysql"], {"schema": schema})
    else:
        key_rows = source.fetch(_KEYS_SQL["postgres_family"], {"schema": schema})
    fk_enforced = kind != "redshift"  # Redshift FKs are informational only
    for row in key_rows:
        t = tables.get(row["table_name"])
        if t is None:
            continue
        if row["constraint_type"] == "PRIMARY KEY":
            t.primary_key.append(row["column_name"])
        elif row["constraint_type"] == "FOREIGN KEY" and row.get("ref_table"):
            t.foreign_keys.append(ForeignKey(
                column=row["column_name"],
                ref_schema=row["ref_schema"],
                ref_table=row["ref_table"],
                ref_column=row["ref_column"],
                enforced=fk_enforced,
            ))

    return list(tables.values())
