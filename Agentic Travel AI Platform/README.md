# Multi-Agent AI Platform

A Streamlit chatbot built with LangGraph and LangChain. It routes each user question to a specialist agent that can call tools for live weather, Wikipedia lookup, travel budget calculations, CSV analysis, SQLite analysis, and document RAG over uploaded files.

The default LLM provider is Groq via `langchain-groq`. The app can also use OpenAI when both an OpenAI API key and model are supplied through `.env` or environment variables. If OpenAI key/model are missing, it falls back to the existing `.env` Groq configuration.

For the detailed system design, see [ARCHITECTURE.md](ARCHITECTURE.md).
For the lessons learned while building and debugging the project, see [PROJECT_LEARNINGS.md](PROJECT_LEARNINGS.md).

## What It Does

1. Routes user messages to the best specialist agent with a hybrid rule-based plus LLM router.
2. Calls external and local tools instead of relying only on model memory.
3. Answers questions over a tourism CSV using guarded pandas expressions.
4. Answers questions over an airline SQLite database using read-only SQL with database-level write denial.
5. Uploads PDF/text/Markdown/image files into a session-scoped FAISS vector store for multimodal document Q&A.
6. Keeps LangGraph conversation state with MongoDB when available, with in-memory fallback.
7. Persists visible chat transcripts locally so a named session can be restored after refresh/login.
8. Shows token usage, provider/model-aware estimated cost, selected agent, tool calls, SQL, pandas code, and retrieved raw data in the UI.

## Current Flow

1. `app.py` configures the Streamlit page and renders sidebar, upload, and chat components.
2. `ui/sidebar.py` initializes session state, tracks tokens/costs, restores named chat sessions, and manages reset.
3. `ui/data_upload.py` saves uploaded documents and calls the RAG ingestion tool.
4. `ui/chat.py` receives a user message and calls the supervisor.
5. `ui/chat.py` checks compact conversation state for pending clarifications and resolved follow-up context, such as the last successful weather location.
6. `agents/supervisor.py` first applies deterministic routing rules for obvious requests, then asks the LLM to classify ambiguous messages as `GENERAL`, `SQL`, `CSV`, `RAG`, or `OUT_OF_DOMAIN`.
7. The selected specialist agent runs as a LangGraph ReAct agent with its tool list and memory checkpointer.
8. Tool calls are executed, intermediate steps are captured, compact state is updated from successful tool results, and the final answer is rendered back into Streamlit.

## Tech Stack

- UI: Streamlit
- Agent orchestration: LangGraph `create_react_agent`
- LLMs: Groq by default, OpenAI optional `.env` override
- Embeddings: local HuggingFace sentence-transformer embeddings
- Vector store: FAISS
- Memory/checkpointing: MongoDB via `langgraph-checkpoint-mongodb`, with `MemorySaver` fallback
- Visible chat transcript store: local JSON under `data/chat_sessions/`
- CSV analysis: pandas with AST validation, no builtins/imports/file I/O, copied DataFrame execution, and timeout guard
- SQL analysis: SQLite read-only connection plus SQLite authorizer guard
- Document parsing: PyMuPDF for PDF text/images, pytesseract for OCR, pdfplumber for tables, optional OpenAI vision captions for images/charts
- External data: Open-Meteo weather API and Wikipedia

## Project Structure

```text
.
|-- app.py                         # Streamlit entry point
|-- config.py                      # Central configuration and shared LLM/embedding/checkpointer factories
|-- conversation_state.py          # Compact pending/follow-up state helpers
|-- guardrails.py                  # Pre-agent task guardrails for out-of-domain requests
|-- schema_registry.py             # Introspects SQL and CSV schemas for routing context
|-- setup_data.py                  # Generates sample tourism CSV and airline SQLite data
|-- requirements.txt               # Python dependencies
|-- .env.example                   # Safe environment template
|-- ARCHITECTURE.md                # Detailed flow and design documentation
|-- agents/
|   |-- supervisor.py              # Hybrid query router and agent cache
|   |-- general_agent.py           # Weather, Wikipedia, and budget agent
|   |-- sql_agent.py               # Airline SQLite agent
|   |-- csv_agent.py               # Tourism CSV agent
|   `-- rag_agent.py               # Document RAG agent
|-- tools/
|   |-- weather.py                 # Open-Meteo tools
|   |-- wiki.py                    # Wikipedia summary tool
|   |-- budget_calc.py             # Demo travel and flight budget calculators
|   |-- sql_tools.py               # Read-only SQL schema/query tools
|   |-- csv_tools.py               # CSV info and guarded pandas execution tools
|   `-- rag_tools.py               # Multimodal document ingestion and FAISS search
|-- ui/
|   |-- sidebar.py                 # Session, token/cost, reset, data status
|   |-- chat.py                    # Chat rendering, streaming, and tool trace display
|   |-- data_upload.py             # Document uploader
|   `-- session_store.py           # Local JSON store for visible chat transcripts
|-- tests/                         # Focused guardrail and routing tests
|-- data/
|   |-- tourism_trends.csv         # Generated tourism dataset
|   |-- airlines.sqlite            # Generated airline database
|   |-- chat_sessions/             # Local visible chat transcripts
|   |-- extracted_assets/          # Extracted images/page renders for multimodal RAG
|   `-- sample_guides/             # Uploaded documents
`-- vectorstore/                   # Persisted FAISS index
```

## Configuration

Copy `.env.example` to `.env`, then fill in whichever provider you want available.

```env
# Optional OpenAI provider. Used only when both values are present.
OPENAI_API_KEY=
OPENAI_MODEL=

# Default fallback provider.
GROQ_API_KEY=
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.0
APP_ENV=development

# Optional pricing override in USD per 1M tokens.
LLM_INPUT_PRICE_PER_MILLION=
LLM_OUTPUT_PRICE_PER_MILLION=
CSV_QUERY_TIMEOUT_SECONDS=5
MAX_UPLOAD_MB=25

# Local embeddings and data paths.
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CSV_DATA_PATH=data/tourism_trends.csv
SQLITE_DATA_PATH=data/airlines.sqlite
VECTORSTORE_PATH=vectorstore/faiss_index

# Multimodal RAG controls.
RAG_ENABLE_OCR=true
RAG_ENABLE_TABLE_EXTRACTION=true
RAG_ENABLE_VISION_CAPTIONS=true
RAG_MAX_IMAGES_PER_PAGE=3

# Optional persistent agent memory.
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=agent_platform
```

Provider configuration is read from `.env` or environment variables. The Streamlit UI does not collect API keys.

Agent memory is checkpointed per specialist agent, for example `session_aadit:sql` and `session_aadit:general`.
This keeps SQL, CSV, RAG, and general tool-call histories separate while preserving one visible chat session.

The UI also keeps a compact structured state object for conversation continuity. This is separate from the full message history. It records things like pending weather clarifications and the last resolved weather location, so follow-ups such as "forecast for next 3 days" can call the weather tool with the previously resolved city instead of asking the user to repeat it.

When `APP_ENV=production`, missing LLM keys or an unavailable MongoDB checkpointer fail loudly instead of silently falling back to weaker runtime behavior.

## Multimodal RAG

Ingestion now creates searchable chunks from multiple modalities:

- Digital PDF text from PyMuPDF
- OCR text from scanned/low-text PDF pages via Tesseract
- Tables extracted with pdfplumber and converted to Markdown-like chunks
- Embedded PDF images and direct image uploads
- Optional OpenAI vision captions for images, charts, diagrams, maps, and screenshots

Each named session writes to its own RAG namespace under `vectorstore/` and `data/extracted_assets/`, so uploaded documents are not mixed across sessions.

For OCR, install the Python dependencies and the Tesseract system binary. On Windows, install Tesseract from its official installer and make sure `tesseract.exe` is on PATH.

For image/chart understanding, provide an OpenAI API key and a vision-capable model in `.env`. Without OpenAI vision, the app still extracts and stores image assets, but semantic chart/image descriptions will be limited.

## How To Run

1. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

2. Generate sample data if needed:

   ```powershell
   python setup_data.py
   ```

3. Start the app:

   ```powershell
   streamlit run app.py
   ```

4. Enter a name in the sidebar, then ask questions.

5. Run tests:

   ```powershell
   pytest
   ```

## Example Questions

- "What's the weather in Tokyo right now?"
- "Compare weather in Delhi, Mumbai, and Goa."
- "What is the average trip cost by season?"
- "Show the top 5 busiest destination airports."
- "Upload a PDF and summarize the key findings."
- "What does the chart on page 4 show?"
- "Extract the main values from the table in the uploaded report."
- "Upload this scanned image and tell me what text it contains."
- "Calculate a trip budget for Shimla for 2 nights for 3 people."

## Current Limitations

- Multimodal RAG depends on optional local tools and/or OpenAI vision. OCR requires the Tesseract binary, and image/chart understanding is strongest when a vision-capable OpenAI model is configured.
- CSV analysis validates generated pandas expressions with an AST allowlist, removes builtins, blocks imports/file I/O, executes against a copied DataFrame, and applies a timeout guard. For stricter production isolation, replace this with a dedicated sandbox service with memory limits or a dataframe query DSL.
- Prompt injection is mitigated with layered controls: pre-agent task guardrails, least-privilege specialist tools, untrusted-content wrapping for RAG/Wikipedia results, explicit agent instructions not to obey retrieved content, and deterministic tests. This reduces risk but does not eliminate prompt injection completely.
- FAISS loading uses local deserialization, so persisted indexes should be treated as trusted local artifacts.
- Pricing is provider/model-aware for known models and can be overridden in `.env`; keep prices updated because providers change pricing over time.
- Streamlit session state is browser-session based; visible transcripts are restored from local JSON only after the user starts the same named session again.
