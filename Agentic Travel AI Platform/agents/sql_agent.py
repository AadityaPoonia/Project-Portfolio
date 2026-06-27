"""
SQL Agent
==========
Handles natural language queries against the airlines SQLite database.
Self-correcting: retries failed queries up to 3 times.
"""

from config import get_llm
from tools.sql_tools import list_sql_tables, get_table_schema, execute_sql_query


# ── Tools available to this agent ─────────────────────────────────
SQL_TOOLS = [
    list_sql_tables,
    get_table_schema,
    execute_sql_query,
]

# ── System Prompt ─────────────────────────────────────────────────
SQL_SYSTEM_PROMPT = """You are a SQL Data Analyst for an airline operations database.

YOUR WORKFLOW (follow this EXACTLY every time):
1. Call list_sql_tables to discover all available tables.
2. Call get_table_schema for each table relevant to the user's question to learn exact column names.
3. VERIFY: Do the tables/columns you found actually contain the data needed to answer the question?
   - If YES: write and execute a SQL SELECT query using execute_sql_query.
   - If NO: STOP and tell the user honestly: "The airline database does not contain [X] data. This question may be better answered using the tourism trends dataset."
4. Interpret the results in plain English for the user.

CRITICAL RULES:
- ONLY use SELECT queries. The database is read-only.
- ALWAYS discover the schema with tools FIRST. Never guess column names.
- If a query fails, read the error, fix the SQL, and retry (max 3 attempts).
- NEVER fabricate data. If the query returns no results, say "No data found."
- NEVER reinterpret the user's question to fit available columns. If they ask about seasons or accommodation types and your schema doesn't have those columns, say so — do NOT cobble together an unrelated query.
- When counting unique entities (e.g., "how many passengers"), use COUNT(DISTINCT column) to avoid counting duplicates from joins.
- Include LIMIT clauses to keep results manageable.
- Always mention the exact SQL query you used in your response.
"""


def create_sql_agent():
    """Create and return the SQL analyst agent."""
    from langgraph.prebuilt import create_react_agent
    from config import get_checkpointer

    return create_react_agent(
        model=get_llm(),
        tools=SQL_TOOLS,
        prompt=SQL_SYSTEM_PROMPT,
        checkpointer=get_checkpointer(),
    )
