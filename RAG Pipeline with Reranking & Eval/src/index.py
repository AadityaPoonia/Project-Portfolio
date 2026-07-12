from __future__ import annotations
import os, json, pickle
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from .config import CFG
from .chunking import DocumentChunk

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize
except Exception:
    TfidfVectorizer = None  # type: ignore
    normalize = None  # type: ignore

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

class VectorIndex:
    """OpenAI embeddings if allowed; TF-IDF fallback. Cosine on L2-normalized rows."""
    def __init__(self, index_dir: Path = CFG.index_dir):
        self.index_dir = index_dir; self.index_dir.mkdir(parents=True, exist_ok=True)
        prefer, has_key = CFG.use_openai_embeddings, bool(os.getenv("OPENAI_API_KEY"))
        self.backend = "openai" if (OpenAI and ((prefer == "true") or (prefer == "auto" and has_key))) else "tfidf"
        self._matrix = None; self._vectorizer = None; self._chunks: List[DocumentChunk] = []

    def _embed_openai(self, texts: List[str]):
        client = OpenAI()  # type: ignore
        res = client.embeddings.create(model="text-embedding-3-small", input=texts)
        vecs = np.array([d.embedding for d in res.data], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        return vecs / norms

    def _embed_tfidf(self, texts: List[str]):
        assert TfidfVectorizer and normalize
        if self._vectorizer is None:
            self._vectorizer = TfidfVectorizer(max_features=4096, ngram_range=(1, 2))
            mat = self._vectorizer.fit_transform(texts)
        else:
            mat = self._vectorizer.transform(texts)
        return normalize(mat).astype("float32")

    def _embed(self, texts: List[str]):
        if self.backend == "openai":
            try:
                return self._embed_openai(texts)
            except Exception as e:
                print({"warning":"embed_fallback_to_tfidf","reason":type(e).__name__})
                self.backend = "tfidf"
                return self._embed_tfidf(texts)
        return self._embed_tfidf(texts)

    async def create_index(self, chunks: List[DocumentChunk]) -> bool:
        self._chunks = list(chunks)
        self._matrix = self._embed([c.text for c in self._chunks])
        self.save(); return True

    async def search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        assert self._matrix is not None and self._chunks, "Index not built"
        qv = self._embed([query])
        q = qv.toarray() if hasattr(qv, "toarray") else np.asarray(qv)
        M = self._matrix.toarray() if hasattr(self._matrix, "toarray") else self._matrix
        sims = (M @ q.T).ravel()
        idxs = sims.argsort()[::-1][: top_k]
        return [ {"chunk": self._chunks[i], "score": float(sims[i])} for i in idxs ]

    def save(self) -> None:
        meta = {"backend": self.backend, "chunks": [
            {"chunk_id": c.chunk_id, "text": c.text, "source": c.source, "metadata": c.metadata, "page_number": c.page_number}
            for c in self._chunks
        ]}
        (self.index_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        with open(self.index_dir / "vectors.pkl","wb") as f:
            pickle.dump({"backend": self.backend, "matrix": self._matrix, "vectorizer": self._vectorizer}, f)

    def load(self) -> bool:
        meta_p, vec_p = self.index_dir / "meta.json", self.index_dir / "vectors.pkl"
        if not (meta_p.exists() and vec_p.exists()): return False
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        self.backend = meta.get("backend", self.backend)
        self._chunks = [DocumentChunk(
            chunk_id=e["chunk_id"], text=e["text"], source=e.get("source","unknown"),
            metadata=e.get("metadata",{}), page_number=e.get("page_number"))
            for e in meta["chunks"]
        ]
        with open(vec_p,"rb") as f: bundle = pickle.load(f)
        self._matrix, self._vectorizer = bundle.get("matrix"), bundle.get("vectorizer")
        return True
