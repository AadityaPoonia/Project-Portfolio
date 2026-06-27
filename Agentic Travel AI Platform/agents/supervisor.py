"""
Supervisor Agent
=================
Routes user queries to the appropriate specialist agent:
  - General Agent: weather, Wikipedia, budget calculations
  - SQL Agent: airline database queries
  - CSV Agent: tourism trends data analysis
  - RAG Agent: document Q&A

Uses LangGraph StateGraph for intelligent routing.
"""

import re

from config import get_llm, resolve_llm_config
from guardrails import GUARDRAIL_MESSAGE, is_out_of_domain_request

from agents.general_agent import create_general_agent
from agents.sql_agent import create_sql_agent
from agents.csv_agent import create_csv_agent
from agents.rag_agent import create_rag_agent


from schema_registry import get_csv_columns_list, get_router_context, get_sql_tables_list

# Build the router prompt dynamically from the actual data sources.
# This means adding new tables or CSVs requires ZERO prompt changes.
_schema_context = get_router_context()
_sql_tables = {name.lower() for name in get_sql_tables_list()}
_csv_columns = {name.lower() for name in get_csv_columns_list()}

RAG_KEYWORDS = {
    "document", "documents", "pdf", "file", "uploaded", "upload",
    "knowledge base", "source", "citation", "summarize this",
}
SQL_KEYWORDS = {
    "flight", "flights", "airline", "airport", "airports", "booking",
    "bookings", "ticket", "tickets", "passenger", "passengers", "fare",
    "boarding", "seat", "aircraft",
}
CSV_KEYWORDS = {
    "season", "tourism", "trip", "trips", "traveler", "travelers",
    "accommodation", "satisfaction", "eco", "carbon", "destination_country",
    "origin_country", "travel_purpose", "total_trip_cost",
}
GENERAL_KEYWORDS = {
    "weather", "forecast", "temperature", "rain", "wiki", "wikipedia",
    "who is", "what is", "budget", "discount", "trip budget", "flight discount",
}
OUT_OF_DOMAIN_KEYWORDS = {
    "python", "javascript", "java", "leetcode", "recipe", "cook",
    "debug this code", "write code", "programming",
}
FOLLOW_UP_KEYWORDS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please",
    "go", "ahead", "continue", "proceed", "do", "it", "that", "one",
    "this", "city", "country", "general", "same", "what", "why", "huh",
}

ROUTER_PROMPT = f"""You are a query router. Given the chat history, your task is to classify the user's LATEST message into ONE of these categories.

IMPORTANT: Each category has its own exclusive data. Routing to the wrong one will produce wrong answers.
You MUST focus exclusively on the final user message. Do not let previous AI responses sway your classification for a new topic.

AVAILABLE DATA SOURCES (auto-discovered from the actual databases):
{_schema_context}

CATEGORIES:
GENERAL - Weather (current, forecast, past, city comparison), Wikipedia/knowledge lookups, travel budget estimation, flight discount calculations, or general travel conversation.
SQL - Questions answerable from the Airlines Database described above. Only route here if the question needs columns that exist in the SQL tables.
CSV - Questions answerable from the Tourism Trends Dataset described above. Only route here if the question needs columns that exist in the CSV.
RAG - Questions about specific uploaded documents, PDFs, or files.
OUT_OF_DOMAIN - Questions completely unrelated to travel, weather, factual lookups, airlines, or documents. Includes: programming, code, math, recipes, generic AI chat.

DECISION PROCESS:
0. Look ONLY at the final user message at the bottom of the conversation.
1. Read the column names in each data source above.
2. Match the final user's question to the data source whose columns can answer it.
3. If the question needs columns that ONLY exist in the CSV (e.g., season, accommodation_type, eco_friendly_trip, satisfaction_rating, carbon_footprint_kg, destination_country) -> CSV
4. If the question needs columns that ONLY exist in SQL (e.g., flight_id, airport_code, fare_class, boarding_no, passenger_id, loyalty_tier, passengers, booking_ref) -> SQL
5. If ambiguous, check which source has the specific column names mentioned.
6. If it asks for code or is off-topic -> OUT_OF_DOMAIN
7. If it asks about documents/PDFs -> RAG
8. Everything else -> GENERAL

Respond with ONLY one word: GENERAL, SQL, CSV, RAG, or OUT_OF_DOMAIN.
"""


def _tokenize(text: str) -> set[str]:
    """Lowercase token set used by deterministic routing rules."""
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))


def _is_short_follow_up(message: str) -> bool:
    """Detect short confirmations or clarifications that depend on prior context."""
    stripped = message.strip().lower()
    if not stripped:
        return False
    if stripped in {"?", "??", "???", "!", "!!"}:
        return True

    tokens = _tokenize(stripped)
    if not tokens:
        return False
    return len(tokens) <= 6 and tokens.issubset(FOLLOW_UP_KEYWORDS)


def _is_short_contextual_reply(message: str) -> bool:
    """Detect short answers like a selected city/name that need prior context."""
    if _is_short_follow_up(message):
        return True

    stripped = message.strip()
    if not stripped:
        return False

    tokens = _tokenize(stripped)
    if not tokens:
        return False

    if any(keyword in stripped.lower() for keyword in OUT_OF_DOMAIN_KEYWORDS):
        return False

    # Handles replies such as "Blida", "Country I guess", or "New Delhi".
    return len(tokens) <= 4 and len(stripped) <= 60


def _contextual_follow_up_route(messages: list) -> str | None:
    """Route short follow-ups using recent non-guardrail conversation context."""
    if not messages:
        return None

    latest_user_msg = messages[-1].get("content", "")
    if not _is_short_contextual_reply(latest_user_msg):
        return None

    for previous in reversed(messages[:-1][-8:]):
        content = str(previous.get("content", "")).lower()
        if "guardrail triggered" in content:
            continue

        route = rule_based_route(content)
        if route and route != "OUT_OF_DOMAIN":
            return route

    return None


def rule_based_route(message: str) -> str | None:
    """
    Route obvious requests without an LLM call.

    Returns None when the message is ambiguous enough to need the LLM router.
    """
    text = message.lower()
    tokens = _tokenize(message)

    if is_out_of_domain_request(message):
        return "OUT_OF_DOMAIN"

    if any(keyword in text for keyword in RAG_KEYWORDS):
        return "RAG"

    if tokens & _csv_columns or any(keyword in text for keyword in CSV_KEYWORDS):
        return "CSV"

    if tokens & _sql_tables or any(keyword in text for keyword in SQL_KEYWORDS):
        return "SQL"

    if any(keyword in text for keyword in GENERAL_KEYWORDS):
        return "GENERAL"

    return None


def route_query(messages: list) -> str:
    """Use the LLM to classify which agent should handle the query based on history."""
    # Aggressively isolate the latest message to prevent LLM history anchoring
    latest_user_msg = messages[-1]["content"] if messages else ""

    deterministic_route = rule_based_route(latest_user_msg)
    if deterministic_route:
        return deterministic_route

    follow_up_route = _contextual_follow_up_route(messages)
    if follow_up_route:
        return follow_up_route

    llm = get_llm()
    
    # Only keep the last 2 messages for coreference context, dropping huge tables
    context_msgs = messages[-3:-1] if len(messages) > 1 else []
    
    strict_prompt = ROUTER_PROMPT + f"\n\n====================\nCRITICAL: YOU MUST CLASSIFY THIS EXACT MESSAGE:\n\"{latest_user_msg}\"\n===================="
    
    full_prompt = [{"role": "system", "content": strict_prompt}] + context_msgs + [{"role": "user", "content": latest_user_msg}]
    
    response = llm.invoke(full_prompt)
    category = response.content.strip().upper()

    # Validate response
    valid_categories = {"GENERAL", "SQL", "CSV", "RAG", "OUT_OF_DOMAIN"}
    if category not in valid_categories:
        # Fallback: try to extract a valid category
        for cat in valid_categories:
            if cat in category:
                return cat
        return "GENERAL"

    return category


# ── Agent cache (create once, reuse) ──────────────────────────────
_agents = {}


def _get_agent_cache_key(
    agent_type: str,
) -> tuple[str, str, str, str]:
    """Cache agents per resolved provider/model/key from environment configuration."""
    llm_config = resolve_llm_config()
    return (
        agent_type,
        llm_config["provider"],
        llm_config["model"],
        llm_config["api_key"],
    )


def get_agent(agent_type: str):
    """Get or create the specified agent type."""
    cache_key = _get_agent_cache_key(agent_type)
    if cache_key not in _agents:
        if agent_type == "GENERAL":
            _agents[cache_key] = create_general_agent()
        elif agent_type == "SQL":
            _agents[cache_key] = create_sql_agent()
        elif agent_type == "CSV":
            _agents[cache_key] = create_csv_agent()
        elif agent_type == "RAG":
            _agents[cache_key] = create_rag_agent()
        else:
            _agents[cache_key] = create_general_agent()
    return _agents[cache_key]


def _build_pending_intent_message(user_message: str, pending_intent: dict) -> str:
    """Give the selected agent enough context to complete a pending clarification."""
    tool_name = pending_intent.get("tool_name", "the relevant tool")
    missing_arg = pending_intent.get("missing_arg", "missing information")
    original_query = pending_intent.get("original_query", "")
    tool_args = pending_intent.get("tool_args", {})

    return (
        "The user is answering a clarification question for an earlier tool call.\n"
        f"Original user request: {original_query}\n"
        f"Pending tool: {tool_name}\n"
        f"Missing argument: {missing_arg}\n"
        f"Previous tool arguments: {tool_args}\n"
        f"User clarification: {user_message}\n\n"
        "Continue the original task using the user's clarification. "
        "Do not reroute or ask the same clarification again unless the clarification is still ambiguous."
    )


def run_agent_query(
    user_message: str,
    history: list,
    session_id: str,
    pending_intent: dict | None = None,
    state_context_message: str | None = None,
):
    """
    Route the query and stream the agent response.
    Returns a generator of events from the selected agent.
    Also returns the agent_type for UI display.
    """
    if pending_intent:
        agent_type = pending_intent.get("agent_type", "GENERAL")
        agent_message = _build_pending_intent_message(user_message, pending_intent)
    elif is_out_of_domain_request(user_message):
        agent_type = "OUT_OF_DOMAIN"
        agent_message = user_message
    else:
        routing_messages = history + [{"role": "user", "content": user_message}]
        agent_type = route_query(routing_messages)
        agent_message = state_context_message or user_message
    
    if agent_type == "OUT_OF_DOMAIN":
        from langchain_core.messages import AIMessage
        def ood_stream():
            msg = AIMessage(content="🛡️ **Guardrail Triggered:** I am a specialized Travel & Tourism AI. I cannot assist with programming, coding, math, or other out-of-domain requests. Please ask me about weather, airlines, tourism data, or general factual knowledge!")
            msg = AIMessage(content=GUARDRAIL_MESSAGE)
            # Mimic the langgraph event structure
            yield {"agent": {"messages": [msg]}}
        # We return "GENERAL" visually so the UI doesn't crash on an unknown icon
        return "GENERAL", ood_stream()
    
    agent = get_agent(agent_type)
    agent_thread_id = f"{session_id}:{agent_type.lower()}"
    config = {"configurable": {"thread_id": agent_thread_id}}

    if agent_type == "RAG":
        from tools.rag_tools import set_rag_namespace
        set_rag_namespace(session_id)

    return agent_type, agent.stream(
        {"messages": [("user", agent_message)]},
        config=config,
    )
