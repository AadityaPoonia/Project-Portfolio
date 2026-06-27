"""
Sidebar Component
==================
Token/cost tracker, session controls, and data source status.
"""

import re
import shutil

import streamlit as st

from conversation_state import default_conversation_state
from config import calculate_cost


def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "messages": [],
        "user_name": None,
        "session_id": None,
        "pending_intent": None,
        "conversation_state": default_conversation_state(),
        "token_usage": {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "message_count": 0,
            "agent_calls": 0,
            "history": [],  # Per-message breakdown
        },
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def update_token_usage(
    input_tokens: int,
    output_tokens: int,
    agent_type: str = "",
    provider: str | None = None,
    model: str | None = None,
):
    """Update the session token counters after an LLM call."""
    usage = st.session_state.token_usage
    cost = calculate_cost(input_tokens, output_tokens, provider, model)
    usage["total_input_tokens"] += input_tokens
    usage["total_output_tokens"] += output_tokens
    usage["total_cost_usd"] += cost
    usage["message_count"] += 1
    usage["agent_calls"] += 1

    # Record per-message history
    usage["history"].append({
        "agent": agent_type,
        "provider": provider or "",
        "model": model or "",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
    })


def render_sidebar():
    """Render the complete sidebar with session controls and token tracking."""
    with st.sidebar:
        # ── Header ────────────────────────────────────────────────
        st.markdown("## 🤖 Agent Platform")
        st.markdown("---")

        # ── Session Controls ──────────────────────────────────────
        if not st.session_state.user_name:
            st.markdown("### 🔑 Start Session")
            with st.form("login_form", clear_on_submit=False):
                name_input = st.text_input(
                    "Enter your name:",
                    placeholder="e.g. Aadit",
                    key="name_input",
                )
                submitted = st.form_submit_button(
                    "Start Session", type="primary", use_container_width=True
                )
                if submitted:
                    if name_input and name_input.strip():
                        st.session_state.user_name = name_input.strip()
                        st.session_state.session_id = f"session_{name_input.strip().lower().replace(' ', '_')}"
                        from ui.session_store import load_session_messages
                        st.session_state.messages = load_session_messages(st.session_state.session_id)
                        st.rerun()
                    else:
                        st.warning("Please enter your name.")
        else:
            st.success(f"**{st.session_state.user_name}**")
            st.caption(f"Session: `{st.session_state.session_id}`")

            st.markdown("---")

            # ── Token Usage & Cost Tracker ────────────────────────
            st.markdown("### 📊 Token Usage")

            usage = st.session_state.token_usage

            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Input Tokens",
                    f"{usage['total_input_tokens']:,}",
                )
            with col2:
                st.metric(
                    "Output Tokens",
                    f"{usage['total_output_tokens']:,}",
                )

            total_tokens = usage['total_input_tokens'] + usage['total_output_tokens']
            st.metric(
                "Total Tokens",
                f"{total_tokens:,}",
            )

            st.markdown("### 💰 Estimated Cost")
            st.metric(
                "Session Cost (USD)",
                f"${usage['total_cost_usd']:.6f}",
            )

            st.markdown("### 📈 Session Stats")
            col3, col4 = st.columns(2)
            with col3:
                st.metric("Messages", usage["message_count"])
            with col4:
                st.metric("Agent Calls", usage["agent_calls"])

            # ── Per-message breakdown (expandable) ────────────────
            if usage["history"]:
                with st.expander("Per-Message Breakdown", expanded=False):
                    for i, entry in enumerate(usage["history"], 1):
                        agent_badge = entry.get("agent", "?")
                        st.markdown(
                            f"**#{i}** [{agent_badge}] "
                            f"{entry.get('provider', '?')}/{entry.get('model', '?')} | "
                            f"In: {entry['input_tokens']:,} | "
                            f"Out: {entry['output_tokens']:,} | "
                            f"${entry['cost']:.6f}"
                        )

            st.markdown("---")

            # ── Data Sources Status ───────────────────────────────
            st.markdown("### 📁 Data Sources")

            from config import CSV_DATA_PATH, SQLITE_DATA_PATH
            from pathlib import Path
            import sqlite3

            # CSV status
            if CSV_DATA_PATH.exists():
                import pandas as pd
                try:
                    row_count = len(pd.read_csv(str(CSV_DATA_PATH)))
                    st.markdown(f"✅ Tourism CSV ({row_count:,} rows)")
                except Exception:
                    st.markdown("✅ Tourism CSV (loaded)")
            else:
                st.markdown("❌ Tourism CSV (not found)")

            # SQLite status
            if SQLITE_DATA_PATH.exists():
                try:
                    conn = sqlite3.connect(str(SQLITE_DATA_PATH))
                    tables = conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
                    ).fetchone()[0]
                    conn.close()
                    st.markdown(f"✅ Airlines DB ({tables} tables)")
                except Exception:
                    st.markdown("✅ Airlines DB (loaded)")
            else:
                st.markdown("❌ Airlines DB (not found)")

            # RAG status
            from tools.rag_tools import get_rag_index_path
            vs_path = Path(get_rag_index_path(st.session_state.session_id))
            if vs_path.exists() and (vs_path / "index.faiss").exists():
                st.markdown("✅ RAG Index (ready)")
            else:
                st.markdown("🟠 RAG Index (empty)")

            st.markdown("---")

            # ── Reset Session Button ──────────────────────────────
            if st.button(
                "🔄 Reset Session",
                type="secondary",
                use_container_width=True,
            ):
                _reset_session()
                st.rerun()


def _clear_mongo_checkpoints(session_id: str):
    """Delete LangGraph checkpoint data from MongoDB for a given session."""
    if not session_id:
        return
    try:
        from config import get_mongo_client, MONGODB_DB_NAME
        client = get_mongo_client()
        if client is not None:
            db = client[MONGODB_DB_NAME]
            thread_filter = {
                "$or": [
                    {"thread_id": session_id},
                    {"thread_id": {"$regex": f"^{re.escape(session_id)}:"}},
                ]
            }
            for collection_name in ["checkpoints", "checkpoint_writes"]:
                try:
                    db[collection_name].delete_many(thread_filter)
                except Exception:
                    pass
    except Exception:
        pass


def _reset_session():
    """Wipe all session state and clear MongoDB checkpoints."""
    session_id = st.session_state.get("session_id")
    _clear_mongo_checkpoints(session_id)
    if session_id:
        from ui.session_store import delete_session_messages
        from config import DATA_DIR
        from tools.rag_tools import clear_rag_namespace

        delete_session_messages(session_id)
        clear_rag_namespace(session_id)

        upload_session = re.sub(r"[^a-zA-Z0-9_.-]+", "_", session_id).strip("_") or "session"
        upload_dir = DATA_DIR / "sample_guides" / upload_session
        if upload_dir.exists():
            shutil.rmtree(upload_dir)

    # Also clear the cached agents so they get fresh checkpointers
    from agents.supervisor import _agents
    _agents.clear()

    # Clear all session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
