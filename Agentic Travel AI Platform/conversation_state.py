"""
Structured conversation state helpers.

LangGraph checkpoints store message history, but the UI still benefits from a
small explicit state object for resolved entities and pending follow-ups.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


WEATHER_TOOL_NAMES = {"get_current_weather", "get_forecast", "get_past_weather"}

WEATHER_FOLLOW_UP_TERMS = {
    "weather",
    "forecast",
    "temperature",
    "temp",
    "rain",
    "raining",
    "precipitation",
    "wind",
    "humidity",
    "today",
    "tomorrow",
    "tonight",
    "now",
    "days",
    "day",
    "week",
}

TIME_CONTEXT_TERMS = {
    "next",
    "the",
    "this",
    "today",
    "tomorrow",
    "tonight",
    "now",
    "current",
    "coming",
    "upcoming",
    "day",
    "days",
    "week",
    "weeks",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
}

CONTEXT_LOCATION_TERMS = {
    "that",
    "this",
    "there",
    "same",
    "it",
    "city",
    "place",
    "location",
}

DEFAULT_CONVERSATION_STATE = {
    "last_agent": None,
    "last_tool": None,
    "last_tool_args": {},
    "weather": {
        "last_location": None,
        "last_tool": None,
        "last_tool_args": {},
    },
}


def default_conversation_state() -> dict[str, Any]:
    """Return a fresh state object for one UI session."""
    return deepcopy(DEFAULT_CONVERSATION_STATE)


def normalize_conversation_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Merge older/incomplete state with the current default schema."""
    normalized = default_conversation_state()
    if not isinstance(state, dict):
        return normalized

    for key, value in state.items():
        if key == "weather" and isinstance(value, dict):
            normalized["weather"].update(value)
        elif key in normalized:
            normalized[key] = value
    return normalized


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def _first_token_after(text: str, marker: str) -> str:
    lower = text.lower()
    if marker not in lower:
        return ""
    after = lower.split(marker, 1)[1].strip()
    match = re.search(r"[a-zA-Z0-9_]+", after)
    return match.group(0) if match else ""


def is_weather_follow_up(user_message: str) -> bool:
    """Return True when a message appears to continue a weather topic."""
    return bool(_tokens(user_message) & WEATHER_FOLLOW_UP_TERMS)


def has_explicit_new_location(user_message: str) -> bool:
    """
    Heuristically detect when the user provided a new location.

    This intentionally does not validate city names. It only avoids overwriting
    explicit requests such as "forecast for Tokyo" with stored context.
    """
    lower = f" {user_message.lower()} "
    for marker in (" in ", " at ", " near ", " around "):
        first = _first_token_after(lower, marker)
        if first and first not in TIME_CONTEXT_TERMS and first not in CONTEXT_LOCATION_TERMS:
            return True

    first_after_for = _first_token_after(lower, " for ")
    if (
        first_after_for
        and first_after_for not in TIME_CONTEXT_TERMS
        and first_after_for not in CONTEXT_LOCATION_TERMS
    ):
        return True

    return False


def build_contextual_user_message(user_message: str, state: dict[str, Any] | None) -> str:
    """
    Add compact resolved-entity context when the latest message is a follow-up.

    The returned text is sent to the selected agent. The visible chat transcript
    still stores the user's original words.
    """
    normalized = normalize_conversation_state(state)
    last_location = normalized["weather"].get("last_location")

    if not last_location:
        return user_message
    if not is_weather_follow_up(user_message):
        return user_message
    if has_explicit_new_location(user_message):
        return user_message

    return (
        "Conversation state for this turn:\n"
        f"- Last resolved weather location: {last_location}\n\n"
        "The latest user message appears to be a weather follow-up and does not "
        "introduce a new explicit location. Use the stored location when calling "
        "weather tools. Do not ask the user to reconfirm the location unless this "
        "message introduces a genuinely different ambiguous location.\n\n"
        f"Latest user message: {user_message}"
    )


def _extract_resolved_weather_location(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: str,
) -> str | None:
    if "AMBIGUITY_DETECTED" in tool_result:
        return None

    patterns = (
        r"Current weather in (?P<location>.*?):",
        r"\d+-day forecast for (?P<location>.*?):",
        r"Past weather in (?P<location>.*?) on ",
    )
    for pattern in patterns:
        match = re.search(pattern, tool_result)
        if match:
            return match.group("location").strip()

    city = tool_args.get("city")
    if tool_name in WEATHER_TOOL_NAMES and city:
        return str(city).strip()
    return None


def update_conversation_state_from_tool(
    state: dict[str, Any] | None,
    agent_type: str,
    tool_name: str,
    tool_args: dict[str, Any] | None,
    tool_result: str,
) -> dict[str, Any]:
    """Return updated state after observing a tool result."""
    normalized = normalize_conversation_state(state)
    args = dict(tool_args or {})

    if tool_name:
        normalized["last_agent"] = agent_type
        normalized["last_tool"] = tool_name
        normalized["last_tool_args"] = args

    if tool_name in WEATHER_TOOL_NAMES:
        location = _extract_resolved_weather_location(tool_name, args, tool_result)
        if location:
            normalized["weather"] = {
                "last_location": location,
                "last_tool": tool_name,
                "last_tool_args": args,
            }

    return normalized
