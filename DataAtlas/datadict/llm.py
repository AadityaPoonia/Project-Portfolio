"""Thin LLM client for Phases 3-4 (OpenAI chat completions, JSON-mode).

The LLM NEVER gets credentials, SQL execution, or network access to any
database. It receives already-masked metadata read from the sandbox and
returns text. That is the entire interface.

Modules take a `complete_json` callable so tests inject a fake; the real
client is only constructed at CLI entry points.
"""
import json
import os


DEFAULT_MODEL = "gpt-4o-mini"


class LLMClient:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit(
                "OPENAI_API_KEY is not set. Add it to .env on the machine "
                "running this job (it is only needed for describe/narrate steps).")
        try:
            from openai import OpenAI
        except ImportError:
            raise SystemExit("The 'openai' package is missing: "
                             ".venv/bin/pip install -r requirements.txt")
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._client = OpenAI(api_key=api_key)

    def complete_json(self, system: str, user: str) -> dict:
        """One JSON-mode chat completion. Raises on malformed output."""
        resp = self._client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return json.loads(resp.choices[0].message.content)
