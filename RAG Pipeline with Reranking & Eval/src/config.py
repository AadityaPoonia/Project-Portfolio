from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(override=False)

def _env(name: str, default: str) -> str:
    v = os.getenv(name, default)
    return default if v is None else str(v)

@dataclass(frozen=True)
class Config:
    index_dir: Path = Path(_env("INDEX_DIR", ".rag_index"))
    chunk_size: int = int(_env("CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(_env("CHUNK_OVERLAP", "200"))
    top_k: int = int(_env("TOP_K", "4"))
    sim_threshold: float = float(_env("SIMILARITY_THRESHOLD", "0.22"))
    rerank_enabled: bool = _env("RERANK_ENABLED", "true").lower() in {"1","true","yes"}
    rerank_top_n: int = int(_env("RERANK_TOP_N", "20"))
    rerank_model: str = _env("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    ce_w: float = float(_env("RERANK_WEIGHTS", "0.6,0.25,0.15").split(",")[0])
    vec_w: float = float(_env("RERANK_WEIGHTS", "0.6,0.25,0.15").split(",")[1])
    bm25_w: float = float(_env("RERANK_WEIGHTS", "0.6,0.25,0.15").split(",")[2])
    # New toggles
    use_openai_embeddings: str = _env("USE_OPENAI_EMBEDDINGS", "auto").lower()   # auto|true|false
    use_openai_generation: str = _env("USE_OPENAI_GENERATION", "auto").lower()   # auto|true|false

CFG = Config()
