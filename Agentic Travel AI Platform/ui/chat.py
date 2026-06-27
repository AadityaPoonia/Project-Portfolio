"""
Chat Component
================
Main chat interface with streaming responses and expandable thinking panels.
"""

import streamlit as st
from agents.supervisor import run_agent_query
from conversation_state import (
    build_contextual_user_message,
    default_conversation_state,
    update_conversation_state_from_tool,
)
from config import resolve_llm_config
from ui.sidebar import update_token_usage
from ui.session_store import save_session_messages


CHAT_CONTEXT_MESSAGES = 10


# Agent type display names and icons
AGENT_LABELS = {
    "GENERAL": ("General Agent", "🌤️"),
    "SQL": ("SQL Agent", "✈️"),
    "CSV": ("CSV Agent", "📊"),
    "RAG": ("RAG Agent", "📄"),
}

PENDING_TOOL_CONFIG = {
    "get_current_weather": {
        "agent_type": "GENERAL",
        "missing_arg": "city",
    },
    "get_forecast": {
        "agent_type": "GENERAL",
        "missing_arg": "city",
    },
    "get_past_weather": {
        "agent_type": "GENERAL",
        "missing_arg": "city",
    },
}

NEW_INTENT_TERMS = {
    "flight", "flights", "airline", "airport", "airports", "ticket",
    "csv", "dataset", "season", "tourism", "document", "pdf", "upload",
    "python", "code", "programming",
}


def _simple_tokens(text: str) -> list[str]:
    return [part.strip(".,!?;:()[]{}\"'").lower() for part in text.split() if part.strip()]


def _is_pending_completion_candidate(user_input: str) -> bool:
    """Return True for short replies that likely answer a clarification."""
    stripped = user_input.strip()
    if stripped in {"?", "??", "???", "!", "!!"}:
        return True
    if "?" in stripped:
        return False

    tokens = [token for token in _simple_tokens(stripped) if token]
    if not tokens:
        return False
    if any(token in NEW_INTENT_TERMS for token in tokens):
        return False
    return len(tokens) <= 6 and len(stripped) <= 80


def _pending_intent_for_request(user_input: str) -> dict | None:
    pending_intent = st.session_state.get("pending_intent")
    if pending_intent and _is_pending_completion_candidate(user_input):
        return pending_intent
    if pending_intent:
        tokens = _simple_tokens(user_input)
        if any(token in NEW_INTENT_TERMS for token in tokens):
            st.session_state.pending_intent = None
    return None


def _record_pending_intent(
    user_input: str,
    tool_name: str,
    tool_args: dict,
    tool_result: str,
) -> None:
    """Store missing-argument state when a tool asks for clarification."""
    if "AMBIGUITY_DETECTED" not in tool_result:
        return

    tool_config = PENDING_TOOL_CONFIG.get(tool_name)
    if not tool_config:
        return

    st.session_state.pending_intent = {
        "agent_type": tool_config["agent_type"],
        "tool_name": tool_name,
        "missing_arg": tool_config["missing_arg"],
        "tool_args": tool_args,
        "original_query": user_input,
    }


def _clear_pending_intent_if_resolved(tool_name: str, tool_result: str) -> None:
    """Clear pending state once the selected tool returns a real result."""
    pending_intent = st.session_state.get("pending_intent")
    if not pending_intent or pending_intent.get("tool_name") != tool_name:
        return
    if "AMBIGUITY_DETECTED" in tool_result:
        return

    success_markers = (
        "Current weather in ",
        "-day forecast for ",
        "Past weather in ",
    )
    if any(marker in tool_result for marker in success_markers):
        st.session_state.pending_intent = None


def render_chat():
    """Render the main chat interface."""
    if not st.session_state.user_name:
        _render_welcome()
        return

    # ── Show guidance when chat is empty ───────────────────────────
    if not st.session_state.messages:
        _render_post_login_guide()

    # ── Display Chat History ──────────────────────────────────────
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Show expandable thinking panel for assistant messages
            if message["role"] == "assistant" and message.get("thinking"):
                _render_thinking_panel(message["thinking"])

    # ── Handle New User Input ─────────────────────────────────────
    if user_input := st.chat_input("Ask about weather, travel data, flights, or documents..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Generate response
        with st.chat_message("assistant"):
            _stream_response(user_input)


def _render_welcome():
    """Show welcome screen when no session is active."""
    st.markdown(
        """
        <div style="text-align: center; padding: 60px 20px;">
            <h1 style="font-size: 2.5em;">🤖 Multi-Agent AI Platform</h1>
            <p style="font-size: 1.2em; color: #888; max-width: 600px; margin: 0 auto;">
                A state-of-the-art agentic system powered by LangGraph and Llama 3.3 on Groq.
                Ask about weather, analyze travel data, query airline databases,
                or search your uploaded documents.
            </p>
            <br>
            <p style="color: #aaa;">👈 Enter your name in the sidebar to begin</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Feature cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("#### 🌤️ Weather")
        st.caption("Real-time weather, forecasts, and city comparisons")
    with col2:
        st.markdown("#### 📊 Tourism Data")
        st.caption("10K travel records, analyzed with pandas")
    with col3:
        st.markdown("#### ✈️ Airlines DB")
        st.caption("Flights, bookings, passengers — queried with SQL")
    with col4:
        st.markdown("#### 📄 Documents")
        st.caption("Upload PDFs for RAG-powered Q&A")


def _render_post_login_guide():
    """Show helpful guidance when the user has logged in but hasn't chatted yet."""
    name = st.session_state.user_name
    st.markdown(f"### Welcome, {name}! 👋")
    st.markdown(
        "I'm your **Travel & Tourism AI Assistant**. "
        "I have access to live weather APIs, a 10K-row tourism dataset, "
        "a full airline operations database, and a document knowledge base. "
        "Here are some things you can ask me:"
    )
    st.markdown("")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            "**🌤️ Weather**\n"
            "- _What's the weather in Tokyo right now?_\n"
            "- _Compare weather in Delhi, Mumbai, and Goa_\n"
            "- _7-day forecast for Manali_\n"
        )
        st.markdown(
            "**✈️ Airlines (SQL)**\n"
            "- _How many flights are there to London?_\n"
            "- _Show me the top 5 busiest airports_\n"
            "- _Average booking amount by fare class_\n"
        )
    with col2:
        st.markdown(
            "**📊 Tourism Data (CSV)**\n"
            "- _What's the average trip cost by season?_\n"
            "- _Top 10 most visited countries_\n"
            "- _Satisfaction ratings for eco-friendly trips_\n"
        )
        st.markdown(
            "**📄 Documents (RAG)**\n"
            "- Upload a PDF via the sidebar, then ask questions\n"
            "- _What does the document say about...?_\n"
            "- _Summarize the key findings_\n"
        )

    st.info("💡 **Tip:** I'll show you exactly which tools and queries I use in expandable panels under each response.", icon="💡")


def _stream_response(user_input: str):
    """Stream the agent response with real-time updates."""
    message_placeholder = st.empty()
    full_response = ""
    thinking_data = {
        "agent_type": "",
        "tool_calls": [],
        "tool_results": [],
        "sql_query": None,
        "pandas_code": None,
    }

    try:
        # Extract clean history for routing (excluding 'thinking' metadata)
        recent_messages = st.session_state.messages[-(CHAT_CONTEXT_MESSAGES + 1):-1]
        history = [
            {"role": m["role"], "content": m["content"]} 
            for m in recent_messages
        ]

        pending_intent = _pending_intent_for_request(user_input)
        conversation_state = st.session_state.get("conversation_state")
        if conversation_state is None:
            conversation_state = default_conversation_state()
            st.session_state.conversation_state = conversation_state
        contextual_user_message = build_contextual_user_message(user_input, conversation_state)
        state_context_message = (
            contextual_user_message
            if contextual_user_message != user_input and not pending_intent
            else None
        )

        # Route and get agent stream
        active_llm = resolve_llm_config()
        agent_type, event_stream = run_agent_query(
            user_input,
            history,
            st.session_state.session_id,
            pending_intent=pending_intent,
            state_context_message=state_context_message,
        )
        thinking_data["agent_type"] = agent_type
        label, icon = AGENT_LABELS.get(agent_type, ("Agent", "🤖"))

        # Expandable thinking panel
        with st.status(f"{icon} {label} processing...", expanded=False) as status:
            total_input_tokens = 0
            total_output_tokens = 0

            for event in event_stream:
                # ── Agent events (LLM decisions) ──────────────────
                if "agent" in event:
                    msg = event["agent"]["messages"][0]

                    # Track token usage from response metadata
                    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                        um = msg.usage_metadata
                        total_input_tokens += um.get("input_tokens", 0)
                        total_output_tokens += um.get("output_tokens", 0)

                    # Log tool calls
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = tc["name"]
                            tool_args = tc["args"]
                            thinking_data["tool_calls"].append({
                                "name": tool_name,
                                "args": tool_args,
                            })
                            status.write(f"🔧 **Calling:** `{tool_name}`")
                            # Show args in compact form
                            args_str = str(tool_args)
                            if len(args_str) > 150:
                                args_str = args_str[:150] + "..."
                            status.write(f"Args: `{args_str}`")

                    # Accumulate text response
                    if msg.content:
                        full_response += msg.content
                        message_placeholder.markdown(full_response + " ◾")

                # ── Tool events (tool outputs) ────────────────────
                if "tools" in event:
                    tool_msg = event["tools"]["messages"][0]
                    content = str(tool_msg.content)

                    # Extract SQL query if present
                    if "SQL_QUERY_USED:" in content:
                        lines = content.split("\n")
                        for line in lines:
                            if line.startswith("SQL_QUERY_USED:"):
                                thinking_data["sql_query"] = line.replace("SQL_QUERY_USED:", "").strip()

                    # Extract pandas code if present
                    if "PANDAS_CODE_USED:" in content:
                        lines = content.split("\n")
                        for line in lines:
                            if line.startswith("PANDAS_CODE_USED:"):
                                thinking_data["pandas_code"] = line.replace("PANDAS_CODE_USED:", "").strip()

                    last_tool_call = thinking_data["tool_calls"][-1] if thinking_data["tool_calls"] else {}
                    tool_name = last_tool_call.get("name", "")
                    tool_args = last_tool_call.get("args", {})
                    _record_pending_intent(user_input, tool_name, tool_args, content)
                    _clear_pending_intent_if_resolved(tool_name, content)
                    st.session_state.conversation_state = update_conversation_state_from_tool(
                        st.session_state.get("conversation_state"),
                        agent_type,
                        tool_name,
                        tool_args,
                        content,
                    )

                    # Show truncated result in thinking panel
                    result_preview = content[:300] + ("..." if len(content) > 300 else "")
                    thinking_data["tool_results"].append(result_preview)
                    status.write(f"📝 **Result:** `{result_preview[:200]}...`")

            status.update(label=f"{icon} {label} - Done", state="complete", expanded=False)

        # ── Update UI ─────────────────────────────────────────────
        message_placeholder.markdown(full_response)

        # Update token tracking
        if total_input_tokens > 0 or total_output_tokens > 0:
            update_token_usage(
                total_input_tokens,
                total_output_tokens,
                agent_type,
                provider=active_llm["provider"],
                model=active_llm["model"],
            )

        # Show thinking panel
        if thinking_data["tool_calls"]:
            _render_thinking_panel(thinking_data)

        # Save to history
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "thinking": thinking_data if thinking_data["tool_calls"] else None,
        })
        save_session_messages(st.session_state.session_id, st.session_state.messages)

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "ResourceExhausted" in error_msg:
            st.error(
                "Rate limit reached. Please wait a moment and try again. "
                "The free tier has limited requests per minute."
            )
        else:
            st.error(f"Error: {error_msg}")

        st.session_state.messages.append({
            "role": "assistant",
            "content": f"*Error: {error_msg}*",
            "thinking": None,
        })
        save_session_messages(st.session_state.session_id, st.session_state.messages)


def _render_thinking_panel(thinking: dict):
    """Render the expandable 'Agent's Approach' panel."""
    agent_type = thinking.get("agent_type", "")
    label, icon = AGENT_LABELS.get(agent_type, ("Agent", "🤖"))

    with st.expander(f"🔍 {label}'s Approach (click to expand)", expanded=False):
        # Show SQL query if present
        if thinking.get("sql_query"):
            st.markdown("**SQL Query:**")
            st.code(thinking["sql_query"], language="sql")

        # Show pandas code if present
        if thinking.get("pandas_code"):
            st.markdown("**Pandas Code:**")
            st.code(thinking["pandas_code"], language="python")

        # Show tool calls
        if thinking.get("tool_calls"):
            st.markdown("**Tools Used:**")
            for tc in thinking["tool_calls"]:
                st.markdown(f"- 🔧 `{tc['name']}`")

        # Show tool results
        if thinking.get("tool_results"):
            st.markdown("**Raw Data Retrieved:**")
            for result in thinking["tool_results"]:
                st.text(result[:500])
