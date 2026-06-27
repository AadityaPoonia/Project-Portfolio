"""
Wikipedia Tool
===============
Clean Wikipedia lookup tool for general knowledge queries.
"""

import wikipedia
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from guardrails import format_untrusted_content


class WikiInput(BaseModel):
    query: str = Field(description="The exact search string to query on Wikipedia. Example: 'Cristiano Ronaldo'")
    dummy: str = Field(default="", description="Leave this empty string always")


@tool(args_schema=WikiInput)
def fetch_wiki_summary(query: str, dummy: str = "") -> str:
    """Search Wikipedia for factual information about a topic.
    Use this tool when the user asks general knowledge questions like
    'What is X?', 'Tell me about Y', or 'Who is Z?'."""
    try:
        page = wikipedia.page(query, auto_suggest=False)
        summary = page.summary[:800].encode('ascii', 'ignore').decode('ascii')
        wrapped_summary = format_untrusted_content(
            summary,
            source_label=page.url,
            content_type="wikipedia summary",
        )
        return (
            f"TITLE: {page.title}\n"
            f"URL: {page.url}\n"
            f"SUMMARY:\n{wrapped_summary}"
        )
    except wikipedia.exceptions.DisambiguationError as e:
        options = ", ".join(e.options[:5]).encode('ascii', 'ignore').decode('ascii')
        return (
            f"AMBIGUITY_DETECTED: '{query}' could refer to multiple topics: "
            f"{options}. Please ask the user to be more specific."
        )
    except wikipedia.exceptions.PageError:
        return f"No Wikipedia page found for '{query}'."
    except Exception as e:
        return f"Error searching Wikipedia: {e}"
