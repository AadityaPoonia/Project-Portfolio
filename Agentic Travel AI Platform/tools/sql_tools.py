"""
SQL Tools (Read-Only)
======================
Tools for querying the airlines SQLite database using natural language.
All queries are executed in READ-ONLY mode with safety guardrails.
"""

import re
import sqlite3
from pathlib import Path

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from config import SQLITE_DATA_PATH

# ── Blocked SQL patterns (security) ──────────────────────────────
BLOCKED_PATTERNS = re.compile(
    r"\b(DROP|DELETE|ALTER|INSERT|UPDATE|CREATE|ATTACH|DETACH|REPLACE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
READ_QUERY_PATTERN = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

SQLITE_DENY_ACTIONS = {
    sqlite3.SQLITE_INSERT,
    sqlite3.SQLITE_UPDATE,
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_ALTER_TABLE,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_INDEX,
    sqlite3.SQLITE_DROP_TRIGGER,
    sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_INDEX,
    sqlite3.SQLITE_CREATE_TRIGGER,
    sqlite3.SQLITE_CREATE_VIEW,
    sqlite3.SQLITE_ATTACH,
    sqlite3.SQLITE_DETACH,
}


def _quote_identifier(identifier: str) -> str:
    """Safely quote a SQLite identifier already validated against sqlite_master."""
    return '"' + identifier.replace('"', '""') + '"'


def _readonly_authorizer(action, arg1, arg2, db_name, trigger_name):
    """SQLite callback that denies write/schema-changing operations."""
    if action in SQLITE_DENY_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _is_readonly_query(query: str) -> bool:
    """Return True when the query shape is read-only before SQLite execution."""
    if not READ_QUERY_PATTERN.search(query):
        return False
    if BLOCKED_PATTERNS.search(query):
        return False
    return True


def _get_readonly_connection() -> sqlite3.Connection:
    """Open a read-only SQLite connection."""
    db_path = str(SQLITE_DATA_PATH)
    # Use URI mode for read-only access
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ── Input Schemas ─────────────────────────────────────────────────

class SQLQueryInput(BaseModel):
    query: str = Field(description="A valid SQL SELECT query to execute against the airlines database")
    dummy: str = Field(description="Leave this empty string always. MUST be provided.")

class TableNameInput(BaseModel):
    table_name: str = Field(description="Name of the table to inspect")
    dummy: str = Field(description="Leave this empty string always. MUST be provided.")


# ── Tools ─────────────────────────────────────────────────────────

@tool
def list_sql_tables() -> str:
    """List all tables in the airlines database with their row counts.
    Use this first to understand what data is available before writing SQL queries."""
    try:
        conn = _get_readonly_connection()
        cursor = conn.cursor()

        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
        ).fetchall()

        result = "Airlines Database Tables:\n"
        for (table_name,) in tables:
            count = cursor.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}").fetchone()[0]
            result += f"  - {table_name} ({count:,} rows)\n"

        conn.close()
        return result
    except Exception as e:
        return f"Error listing tables: {e}"


@tool(args_schema=TableNameInput)
def get_table_schema(table_name: str, dummy: str = "") -> str:
    """Get the schema (columns, types) and sample rows for a specific table.
    Use this to understand column names and data types before writing a SQL query."""
    try:
        conn = _get_readonly_connection()
        cursor = conn.cursor()

        # Validate table exists
        tables = [
            row[0] for row in
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        if table_name not in tables:
            conn.close()
            return f"Table '{table_name}' not found. Available tables: {', '.join(tables)}"

        # Get column info
        quoted_table = _quote_identifier(table_name)
        columns = cursor.execute(f"PRAGMA table_info({quoted_table})").fetchall()
        col_info = "Columns:\n"
        for col in columns:
            col_info += f"  - {col[1]} ({col[2]})"
            if col[5]:  # Primary key
                col_info += " [PRIMARY KEY]"
            if col[3]:  # Not null
                col_info += " NOT NULL"
            col_info += "\n"

        # Get sample rows
        sample_rows = cursor.execute(f"SELECT * FROM {quoted_table} LIMIT 3").fetchall()
        col_names = [col[1] for col in columns]

        sample_str = "\nSample Data (3 rows):\n"
        for row in sample_rows:
            row_dict = dict(zip(col_names, row))
            sample_str += f"  {row_dict}\n"

        conn.close()
        return f"Schema for '{table_name}':\n{col_info}{sample_str}"
    except Exception as e:
        return f"Error getting schema: {e}"


@tool(args_schema=SQLQueryInput)
def execute_sql_query(query: str, dummy: str = "") -> str:
    """Execute a SQL SELECT query against the airlines database.
    IMPORTANT: Only SELECT queries are allowed. The database is read-only.
    Always include a LIMIT clause to avoid returning too many rows.
    Returns the query results and the exact SQL that was executed.

    Available tables: aircrafts, airports, flights, passengers,
    bookings, tickets, boarding_passes, seat_map
    """
    # ── Safety Check: Block dangerous operations ──────────────────
    if not _is_readonly_query(query):
        return (
            "BLOCKED: Only read-only SELECT queries are allowed. "
            "The database connection also denies write/schema operations."
        )

    # Enforce LIMIT if not present
    if "LIMIT" not in query.upper():
        query = query.rstrip(";") + " LIMIT 50"

    try:
        conn = _get_readonly_connection()
        conn.set_authorizer(_readonly_authorizer)
        cursor = conn.cursor()
        cursor.execute(query)

        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []

        if not rows:
            conn.close()
            return f"SQL_QUERY_USED: {query}\n\nResult: No rows returned. The query executed successfully but found no matching data."

        # Format as readable table
        result_lines = [f"SQL_QUERY_USED: {query}", f"Rows returned: {len(rows)}", ""]

        # Header
        header = " | ".join(columns)
        result_lines.append(header)
        result_lines.append("-" * len(header))

        # Data rows
        for row in rows:
            result_lines.append(" | ".join(str(v) for v in row))

        conn.close()
        return "\n".join(result_lines)

    except sqlite3.OperationalError as e:
        return f"SQL_QUERY_USED: {query}\n\nSQL Error: {e}\n\nPlease check your query syntax and try again."
    except Exception as e:
        return f"SQL_QUERY_USED: {query}\n\nUnexpected error: {e}"
