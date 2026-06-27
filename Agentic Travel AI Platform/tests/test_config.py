from config import calculate_cost, get_model_pricing, resolve_llm_config


def test_openai_override_requires_key_and_model():
    resolved = resolve_llm_config(openai_api_key="sk-test", openai_model="gpt-test")

    assert resolved["provider"] == "openai"
    assert resolved["model"] == "gpt-test"


def test_partial_openai_override_falls_back_to_groq():
    resolved = resolve_llm_config(openai_api_key="sk-test", openai_model="")

    assert resolved["provider"] == "groq"


def test_unknown_model_pricing_is_zero_not_fake():
    pricing = get_model_pricing("openai", "unknown-model")

    assert pricing["source"] == "unknown"
    assert calculate_cost(1000, 1000, "openai", "unknown-model") == 0.0
