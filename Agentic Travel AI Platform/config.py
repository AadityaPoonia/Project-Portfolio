"""
Centralized Configuration Module
=================================
Single source of truth for all models, database connections, and constants.
Loads settings from .env file and initializes shared resources.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load Environment ──────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

# ── API Keys ──────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "agent_platform")
APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"

# ── Model Configuration ──────────────────────────────────────────
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_INPUT_PRICE_PER_MILLION = os.getenv("LLM_INPUT_PRICE_PER_MILLION", "")
LLM_OUTPUT_PRICE_PER_MILLION = os.getenv("LLM_OUTPUT_PRICE_PER_MILLION", "")
RAG_ENABLE_OCR = os.getenv("RAG_ENABLE_OCR", "true").lower() == "true"
RAG_ENABLE_TABLE_EXTRACTION = os.getenv("RAG_ENABLE_TABLE_EXTRACTION", "true").lower() == "true"
RAG_ENABLE_VISION_CAPTIONS = os.getenv("RAG_ENABLE_VISION_CAPTIONS", "true").lower() == "true"
RAG_MAX_IMAGES_PER_PAGE = int(os.getenv("RAG_MAX_IMAGES_PER_PAGE", "3"))
CSV_QUERY_TIMEOUT_SECONDS = int(os.getenv("CSV_QUERY_TIMEOUT_SECONDS", "5"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))

# ── Data Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
CSV_DATA_PATH = PROJECT_ROOT / os.getenv("CSV_DATA_PATH", "data/tourism_trends.csv")
SQLITE_DATA_PATH = PROJECT_ROOT / os.getenv("SQLITE_DATA_PATH", "data/airlines.sqlite")
VECTORSTORE_PATH = PROJECT_ROOT / os.getenv("VECTORSTORE_PATH", "vectorstore/faiss_index")
SAMPLE_GUIDES_DIR = DATA_DIR / "sample_guides"
CHAT_HISTORY_DIR = DATA_DIR / "chat_sessions"
EXTRACTED_ASSETS_DIR = DATA_DIR / "extracted_assets"

# ── Ensure directories exist ─────────────────────────────────────
DATA_DIR.mkdir(exist_ok=True)
SAMPLE_GUIDES_DIR.mkdir(parents=True, exist_ok=True)
CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
VECTORSTORE_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Token Pricing (Groq Llama 3 70B — as of May 2026) ────────────
# Prices per 1 million tokens (USD)
MODEL_PRICING = {
    ("groq", "llama-3.3-70b-versatile"): {
        "input_per_million": 0.59,
        "output_per_million": 0.79,
    },
    ("openai", "gpt-4o-mini"): {
        "input_per_million": 0.15,
        "output_per_million": 0.60,
    },
}

# ── Lazy-Initialized Shared Resources ────────────────────────────
# These are created on first access to avoid import-time side effects.

_llm = None
_llm_config = None
_embeddings = None
_checkpointer = None
_mongo_client = None


def resolve_llm_config(openai_api_key: str | None = None, openai_model: str | None = None) -> dict:
    """
    Resolve the active chat model.

    Priority:
    1. Explicit OpenAI key/model arguments.
    2. OPENAI_API_KEY and OPENAI_MODEL from the environment.
    3. Existing Groq configuration loaded from .env/defaults.
    """
    explicit_openai_key = (openai_api_key or "").strip()
    explicit_openai_model = (openai_model or "").strip()
    env_openai_key = (OPENAI_API_KEY or "").strip()
    env_openai_model = (OPENAI_MODEL or "").strip()

    if IS_PRODUCTION and (env_openai_key or env_openai_model) and not (env_openai_key and env_openai_model):
        raise RuntimeError(
            "Production OpenAI configuration requires both OPENAI_API_KEY and OPENAI_MODEL."
        )

    if explicit_openai_key and explicit_openai_model:
        return {
            "provider": "openai",
            "model": explicit_openai_model,
            "api_key": explicit_openai_key,
        }

    if env_openai_key and env_openai_model:
        return {
            "provider": "openai",
            "model": env_openai_model,
            "api_key": env_openai_key,
        }

    groq_key = (GROQ_API_KEY or "").strip()
    if IS_PRODUCTION and not groq_key:
        raise RuntimeError(
            "Production LLM configuration requires either full OpenAI config or GROQ_API_KEY."
        )

    return {
        "provider": "groq",
        "model": LLM_MODEL,
        "api_key": groq_key,
    }


def get_llm(openai_api_key: str | None = None, openai_model: str | None = None):
    """Get the shared LLM instance, preferring OpenAI when key and model are available."""
    global _llm, _llm_config
    resolved_config = resolve_llm_config(openai_api_key, openai_model)

    if _llm is None or _llm_config != resolved_config:
        if not resolved_config["api_key"]:
            raise RuntimeError(
                f"Missing API key for provider '{resolved_config['provider']}'. "
                "Set OPENAI_API_KEY + OPENAI_MODEL or GROQ_API_KEY in .env."
            )
        if resolved_config["provider"] == "openai":
            from langchain_openai import ChatOpenAI
            _llm = ChatOpenAI(
                model=resolved_config["model"],
                temperature=LLM_TEMPERATURE,
                api_key=resolved_config["api_key"],
            )
        else:
            from langchain_groq import ChatGroq
            _llm = ChatGroq(
                model=resolved_config["model"],
                temperature=LLM_TEMPERATURE,
                api_key=resolved_config["api_key"],
            )
        _llm_config = resolved_config
    return _llm


def get_embeddings():
    """Get the shared embeddings model (HuggingFace Local)."""
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
        )
    return _embeddings


def get_checkpointer():
    """
    Get the MongoDB-backed checkpointer for LangGraph.
    Falls back to in-memory if MongoDB is unavailable.
    """
    global _checkpointer, _mongo_client
    if _checkpointer is None:
        try:
            from pymongo import MongoClient
            from langgraph.checkpoint.mongodb import MongoDBSaver

            _mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
            _mongo_client.admin.command("ping")  # Verify connection

            _checkpointer = MongoDBSaver(
                client=_mongo_client,
                db_name=MONGODB_DB_NAME,
            )
            print(f"[OK] MongoDB connected: {MONGODB_URI}")
        except Exception as e:
            if IS_PRODUCTION:
                raise RuntimeError(
                    f"MongoDB checkpointer is required in production but unavailable: {e}"
                ) from e
            from langgraph.checkpoint.memory import MemorySaver
            _checkpointer = MemorySaver()
            print(f"[WARN] MongoDB unavailable ({e}). Using in-memory checkpointer.")
    return _checkpointer


def get_mongo_client():
    """Get the raw MongoDB client (for direct operations like wiping sessions)."""
    global _mongo_client
    if _mongo_client is None:
        get_checkpointer()  # This initializes the client
    return _mongo_client


def get_model_pricing(provider: str | None = None, model: str | None = None) -> dict:
    """Return per-million-token pricing for the resolved provider/model."""
    if LLM_INPUT_PRICE_PER_MILLION and LLM_OUTPUT_PRICE_PER_MILLION:
        try:
            return {
                "input_per_million": float(LLM_INPUT_PRICE_PER_MILLION),
                "output_per_million": float(LLM_OUTPUT_PRICE_PER_MILLION),
                "source": "env_override",
            }
        except ValueError:
            pass

    resolved = resolve_llm_config()
    provider_key = (provider or resolved["provider"]).lower()
    model_key = (model or resolved["model"]).lower()
    pricing = MODEL_PRICING.get((provider_key, model_key))
    if pricing:
        return {**pricing, "source": "built_in"}

    return {
        "input_per_million": 0.0,
        "output_per_million": 0.0,
        "source": "unknown",
    }


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    provider: str | None = None,
    model: str | None = None,
) -> float:
    """Calculate the estimated cost in USD for a given token count."""
    pricing = get_model_pricing(provider, model)
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]
    return input_cost + output_cost
