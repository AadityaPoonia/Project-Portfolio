from agents.supervisor import route_query, rule_based_route


def test_rule_based_route_csv_for_tourism_columns():
    assert rule_based_route("What is the average trip cost by season?") == "CSV"


def test_rule_based_route_sql_for_airline_terms():
    assert rule_based_route("Show the top 5 busiest airports") == "SQL"


def test_rule_based_route_rag_for_uploaded_documents():
    assert rule_based_route("Summarize the uploaded PDF") == "RAG"


def test_rule_based_route_out_of_domain_for_programming():
    assert rule_based_route("Write Python code for a binary search") == "OUT_OF_DOMAIN"


def test_mixed_weather_and_programming_request_is_guarded():
    message = (
        "the weather is very hot in noida today and im not able to write "
        "the code for fibonacci, can you pls help"
    )

    assert rule_based_route(message) == "OUT_OF_DOMAIN"


def test_write_the_code_for_fibonacci_is_guarded():
    assert rule_based_route("write the code for fibonacci") == "OUT_OF_DOMAIN"


def test_airport_code_is_not_treated_as_programming():
    assert rule_based_route("What is the airport code for Delhi?") == "SQL"


def test_short_confirmation_keeps_weather_context():
    messages = [
        {"role": "user", "content": "What's the weather in Algeria?"},
        {
            "role": "assistant",
            "content": "Would you like weather for Algiers, the capital city of Algeria?",
        },
        {"role": "user", "content": "yeah"},
    ]

    assert route_query(messages) == "GENERAL"


def test_punctuation_follow_up_after_guardrail_keeps_weather_context():
    messages = [
        {"role": "user", "content": "What's the weather in Algeria?"},
        {
            "role": "assistant",
            "content": "Would you like weather for Algiers, the capital city of Algeria?",
        },
        {"role": "user", "content": "yeah"},
        {
            "role": "assistant",
            "content": "Guardrail Triggered: I cannot assist with programming or coding.",
        },
        {"role": "user", "content": "???"},
    ]

    assert route_query(messages) == "GENERAL"


def test_country_clarification_keeps_weather_context():
    messages = [
        {"role": "user", "content": "What's the weather in Algeria?"},
        {
            "role": "assistant",
            "content": "Could you clarify if you mean the country or a city?",
        },
        {"role": "user", "content": "Country i guess"},
    ]

    assert route_query(messages) == "GENERAL"


def test_city_selection_keeps_weather_context():
    messages = [
        {"role": "user", "content": "What's the weather in Algeria?"},
        {
            "role": "assistant",
            "content": "If you need weather information for a specific city, please let me know.",
        },
        {"role": "user", "content": "Blida"},
    ]

    assert route_query(messages) == "GENERAL"
