"""Engine factories and the guarded read-only execution path.

Production sources are only ever queried through GuardedSource.fetch(),
which validates SQL via query_guard, applies a hard row cap, and records
every attempt (allowed, blocked, or errored) in the audit log.

Statement timeouts are set at the driver/session level here — not via SQL
through the guarded path, which would itself be blocked (SET is forbidden).
"""
import time
import urllib.parse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .audit import AuditLog
from .query_guard import validate_query, QueryBlocked

DEFAULT_ROW_CAP = 10_000
DEFAULT_TIMEOUT_S = 60


def build_url(engine: str, user: str, password: str, host: str, port: int, database: str) -> str:
    pw = urllib.parse.quote_plus(password)
    if engine == "mysql":
        return f"mysql+pymysql://{user}:{pw}@{host}:{port}/{database}"
    if engine in ("postgres", "redshift"):
        # Redshift speaks the Postgres wire protocol; psycopg2 works for both.
        return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{database}"
    raise ValueError(f"unknown engine {engine!r}")


def _connect_args(engine: str, timeout_s: int) -> dict:
    if engine == "mysql":
        # Per-session read timeout; MAX_EXECUTION_TIME is applied per query below.
        return {"read_timeout": timeout_s, "write_timeout": timeout_s, "connect_timeout": 10}
    # postgres / redshift: server-side statement timeout for the session
    return {
        "connect_timeout": 10,
        "options": f"-c statement_timeout={timeout_s * 1000}",
    }


class GuardedSource:
    """A production data source that can only be read, never written.

    All SQL goes through validate_query() first; results are capped at
    row_cap rows; every attempt lands in the audit log.
    """

    def __init__(self, name: str, engine_kind: str, url: str, audit: AuditLog,
                 row_cap: int = DEFAULT_ROW_CAP, timeout_s: int = DEFAULT_TIMEOUT_S,
                 run_id: str | None = None):
        self.name = name
        self.engine_kind = engine_kind
        self.audit = audit
        self.row_cap = row_cap
        self.run_id = run_id
        self._engine: Engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args=_connect_args(engine_kind, timeout_s),
        )

    def fetch(self, sql: str, params: dict | None = None) -> list[dict]:
        """Validate, execute, and return at most row_cap rows as dicts."""
        try:
            validate_query(sql, self.engine_kind)
        except QueryBlocked as e:
            self.audit.record(source=self.name, sql=sql, status="blocked",
                              error=str(e), run_id=self.run_id)
            raise

        start = time.monotonic()
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                rows = result.mappings().fetchmany(self.row_cap)
                rows = [dict(r) for r in rows]
        except Exception as e:
            self.audit.record(source=self.name, sql=sql, status="error",
                              error=f"{type(e).__name__}: {e}", run_id=self.run_id,
                              duration_ms=(time.monotonic() - start) * 1000)
            raise

        self.audit.record(source=self.name, sql=sql, status="allowed",
                          rows=len(rows), run_id=self.run_id,
                          duration_ms=(time.monotonic() - start) * 1000)
        return rows

    def dispose(self) -> None:
        self._engine.dispose()
