"""
Session Store
=============
Small JSON persistence layer for visible Streamlit chat history.
LangGraph checkpoints store agent state; this stores what the user sees.
"""

import json
import re
from pathlib import Path

from config import CHAT_HISTORY_DIR


def _session_file(session_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", session_id).strip("_")
    return CHAT_HISTORY_DIR / f"{safe_id or 'session'}.json"


def load_session_messages(session_id: str) -> list[dict]:
    """Load persisted visible chat messages for a session."""
    path = _session_file(session_id)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        messages = payload.get("messages", [])
        if isinstance(messages, list):
            return messages
    except Exception:
        return []
    return []


def save_session_messages(session_id: str, messages: list[dict]) -> None:
    """Persist visible chat messages for a session."""
    path = _session_file(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"session_id": session_id, "messages": messages}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_session_messages(session_id: str) -> None:
    """Delete persisted visible chat messages for a session."""
    path = _session_file(session_id)
    if path.exists():
        path.unlink()
