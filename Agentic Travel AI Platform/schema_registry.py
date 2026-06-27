"""
Schema Registry
================
Dynamically introspects all data sources (SQLite, CSV) at startup
and produces a concise schema summary for the router and agents.

This module NEVER hardcodes column names — it reads them from the
actual databases and files. Adding a new table or CSV requires
zero changes here.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from config import SQLITE_DATA_PATH, CSV_DATA_PATH

# ── Cached schema summaries (computed once, reused forever) ───────
_sql_schema: str | None = None
_csv_schema: str | None = None


def get_sql_schema_summary() -> str:
    """
    Connect to SQLite, read all table names and their columns,
    and return a compact text summary.

    Example output:
        Airlines Database (SQLite):
          aircrafts (10 rows): aircraft_code, model, range_km, seats_total
          airports (15 rows): airport_code, airport_name, city, country, timezone
          ...
    """
    global _sql_schema
    if _sql_schema is not None:
        return _sql_schema

    db_path = Path(SQLITE_DATA_PATH)
    if not db_path.exists():
        _sql_schema = "SQL Database: NOT AVAILABLE (file not found)"
        return _sql_schema

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
        ).fetchall()

        lines = ["Airlines Database (SQLite):"]
        for (table_name,) in tables:
            # Get column names
            columns = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
            col_names = [col[1] for col in columns]

            # Get row count
            row_count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            lines.append(f"  {table_name} ({row_count:,} rows): {', '.join(col_names)}")

        conn.close()
        _sql_schema = "\n".join(lines)
    except Exception as e:
        _sql_schema = f"SQL Database: ERROR reading schema ({e})"

    return _sql_schema


def get_csv_schema_summary() -> str:
    """
    Read the CSV header and basic stats without loading full data.
    Uses nrows=5 for a lightweight read.

    Example output:
        Tourism Trends Dataset (CSV, ~10,000 rows):
          Columns: trip_id, year, month, season, origin_country, ...
          Sample values — season: ['Winter', 'Spring', 'Summer', 'Autumn']
          Sample values — accommodation_type: ['Hotel', 'Resort', 'Hostel', ...]
    """
    global _csv_schema
    if _csv_schema is not None:
        return _csv_schema

    csv_path = Path(CSV_DATA_PATH)
    if not csv_path.exists():
        _csv_schema = "CSV Dataset: NOT AVAILABLE (file not found)"
        return _csv_schema

    try:
        # Read just a small sample for metadata
        df_sample = pd.read_csv(str(csv_path), nrows=5)
        # Get total row count efficiently
        with open(str(csv_path), "r", encoding="utf-8", errors="ignore") as f:
            row_count = sum(1 for _ in f) - 1  # subtract header

        col_names = list(df_sample.columns)

        lines = [f"Tourism Trends Dataset (CSV, ~{row_count:,} rows):"]
        lines.append(f"  Columns: {', '.join(col_names)}")

        # Add sample unique values for key categorical columns
        # (helps the router distinguish this dataset's domain)
        df_full = pd.read_csv(str(csv_path), usecols=[
            c for c in ["season", "accommodation_type", "travel_purpose",
                        "traveler_type", "destination_country"]
            if c in col_names
        ])
        for col in ["season", "accommodation_type", "travel_purpose"]:
            if col in df_full.columns:
                uniques = sorted(df_full[col].dropna().unique().tolist())[:8]
                lines.append(f"  Sample values — {col}: {uniques}")

        _csv_schema = "\n".join(lines)
    except Exception as e:
        _csv_schema = f"CSV Dataset: ERROR reading schema ({e})"

    return _csv_schema


def get_router_context() -> str:
    """
    Combine all data source summaries into a single text block
    for injection into the router prompt.

    This is the ONLY function the supervisor imports.
    """
    parts = []
    parts.append(get_sql_schema_summary())
    parts.append("")
    parts.append(get_csv_schema_summary())
    return "\n".join(parts)


def get_sql_tables_list() -> list[str]:
    """Return just the table names (for validation/quick checks)."""
    db_path = Path(SQLITE_DATA_PATH)
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
            ).fetchall()
        ]
        conn.close()
        return tables
    except Exception:
        return []


def get_csv_columns_list() -> list[str]:
    """Return just the column names (for validation/quick checks)."""
    csv_path = Path(CSV_DATA_PATH)
    if not csv_path.exists():
        return []
    try:
        df = pd.read_csv(str(csv_path), nrows=0)
        return list(df.columns)
    except Exception:
        return []
