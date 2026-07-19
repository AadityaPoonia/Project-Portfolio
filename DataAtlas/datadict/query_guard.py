"""AST-level SQL validation: the extraction job's second line of defence.

Every query the pipeline runs against a production source passes through
validate_query() first. Anything that is not a single, plain, read-only
SELECT / EXPLAIN is rejected — even though the pipeline itself only builds
read queries, this catches mistakes if the code is ever extended.

Fail-closed: parse errors, unknown node types, and anything not explicitly
recognised as safe raise QueryBlocked.
"""
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import expressions as exp

# sqlglot dialect names per source engine
DIALECTS = {"mysql": "mysql", "postgres": "postgres", "redshift": "redshift"}

# Top-level statement types allowed. Everything else is blocked.
_ALLOWED_ROOTS = (exp.Select, exp.Union)

# Plain EXPLAIN only — no options. EXPLAIN ANALYZE *executes* the inner
# statement on Postgres, so it must never pass; stripping exactly the bare
# keyword means "EXPLAIN ANALYZE ..." leaves an unparseable remainder and
# is blocked like everything else.
_EXPLAIN_RE = re.compile(r"^\s*EXPLAIN\s+", re.IGNORECASE)

# Node types that must never appear anywhere in the tree, even nested.
_FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Create, exp.Drop, exp.Alter, exp.TruncateTable,
    exp.Set, exp.SetItem, exp.Command, exp.Transaction, exp.Commit,
    exp.Rollback, exp.Grant, exp.Use, exp.Copy,
    exp.Lock,       # SELECT ... FOR UPDATE / FOR SHARE
    exp.Into,       # SELECT ... INTO new_table
)


class QueryBlocked(Exception):
    """Raised when a query fails validation. Always logged to the audit trail."""


@dataclass
class ValidationResult:
    sql: str
    dialect: str
    statement_type: str


def validate_query(sql: str, engine: str, _allow_explain: bool = True) -> ValidationResult:
    """Validate that `sql` is a single read-only SELECT/EXPLAIN statement.

    Returns a ValidationResult on success, raises QueryBlocked otherwise.
    """
    dialect = DIALECTS.get(engine)
    if dialect is None:
        raise QueryBlocked(f"unknown engine {engine!r}")

    explain_match = _EXPLAIN_RE.match(sql)
    if explain_match:
        if not _allow_explain:
            raise QueryBlocked("nested EXPLAIN")
        inner = validate_query(sql[explain_match.end():], engine, _allow_explain=False)
        return ValidationResult(sql=sql, dialect=dialect,
                                statement_type=f"Explain[{inner.statement_type}]")

    try:
        statements = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as e:
        raise QueryBlocked(f"unparseable SQL: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise QueryBlocked(
            f"expected exactly 1 statement, got {len(statements)} (stacked statements are blocked)"
        )

    root = statements[0]
    if not isinstance(root, _ALLOWED_ROOTS):
        raise QueryBlocked(f"statement type {type(root).__name__} is not SELECT/EXPLAIN")

    for node in root.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise QueryBlocked(f"forbidden construct: {type(node).__name__}")

    return ValidationResult(sql=sql, dialect=dialect, statement_type=type(root).__name__)
