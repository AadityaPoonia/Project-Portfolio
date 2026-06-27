from conversation_state import (
    build_contextual_user_message,
    default_conversation_state,
    has_explicit_new_location,
    update_conversation_state_from_tool,
)


def test_weather_tool_success_stores_resolved_location():
    state = update_conversation_state_from_tool(
        default_conversation_state(),
        "GENERAL",
        "get_current_weather",
        {"city": "Blida"},
        "Current weather in Blida, Algeria: Temperature: 28C",
    )

    assert state["weather"]["last_location"] == "Blida, Algeria"
    assert state["last_tool"] == "get_current_weather"


def test_weather_ambiguity_does_not_store_location():
    state = update_conversation_state_from_tool(
        default_conversation_state(),
        "GENERAL",
        "get_current_weather",
        {"city": "Algeria"},
        "AMBIGUITY_DETECTED: Found multiple locations",
    )

    assert state["weather"]["last_location"] is None


def test_weather_follow_up_gets_previous_location_context():
    state = default_conversation_state()
    state["weather"]["last_location"] = "Algiers, Algeria"

    contextual_message = build_contextual_user_message(
        "Whats the forecast for next 3 days?",
        state,
    )

    assert "Last resolved weather location: Algiers, Algeria" in contextual_message
    assert "Latest user message: Whats the forecast for next 3 days?" in contextual_message


def test_explicit_new_location_is_not_overridden():
    state = default_conversation_state()
    state["weather"]["last_location"] = "Algiers, Algeria"
    user_message = "Whats the forecast for Tokyo?"

    contextual_message = build_contextual_user_message(user_message, state)

    assert contextual_message == user_message


def test_contextual_location_terms_are_not_treated_as_new_locations():
    assert not has_explicit_new_location("weather in that city now")
    assert not has_explicit_new_location("forecast for next 3 days")
    assert has_explicit_new_location("forecast for Tokyo")
