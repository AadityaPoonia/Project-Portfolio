"""Append-only JSONL audit trail of every query attempt, including blocked ones.

One line per event. The log is the evidence for the success criterion
"zero write operations ever reach production through this system".
"""
import json
import hashlib
import os
import threading
from datetime import datetime, timezone

_lock = threading.Lock()


class AuditLog:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def record(self, *, source: str, sql: str, status: str,
               rows: int | None = None, duration_ms: float | None = None,
               error: str | None = None, run_id: str | None = None) -> None:
        """status: 'allowed' | 'blocked' | 'error'"""
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "source": source,
            "status": status,
            "sql_sha256": hashlib.sha256(sql.encode()).hexdigest()[:16],
            "sql": sql,
            "rows": rows,
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
            "error": error,
        }
        line = json.dumps(event, ensure_ascii=False)
        with _lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
