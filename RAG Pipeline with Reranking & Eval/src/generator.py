from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from .config import CFG
from .chunking import DocumentChunk
import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

class AnswerGenerator:
    """Grounded answers; graceful fallback to extractive on API errors or when disabled."""
    def __init__(self):
        prefer = CFG.use_openai_generation  # auto|true|false
        has_key = bool(OpenAI and os.getenv("OPENAI_API_KEY"))
        self.has_openai = (prefer == "true" and has_key) or (prefer == "auto" and has_key)
        self.client = OpenAI() if self.has_openai else None  # type: ignore

    @staticmethod
    def _fmt_ctx(chunks: List[DocumentChunk]) -> str:
        lines = []
        for c in chunks:
            cite = f"[{Path(c.source).name} • {c.chunk_id} • p{c.page_number}]"
            lines.append(f"{cite}\n{c.text.strip()}\n")
        return "\n\n".join(lines)

    @staticmethod
    def _citations(chunks: List[DocumentChunk]) -> List[Dict[str, Any]]:
        return [{"chunk_id": c.chunk_id, "source": Path(c.source).name, "page_number": c.page_number} for c in chunks]

    @staticmethod
    def _should_idk(results: List[Dict[str, Any]]) -> bool:
        if not results: return True
        top = results[0]["score"]
        strong = [r for r in results if r["score"] >= CFG.sim_threshold]
        return top < CFG.sim_threshold or len(strong) < 2

    def _extractive(self, query: str, chunks: List[DocumentChunk]) -> str:
        terms = {t.lower() for t in query.split() if len(t) > 3}
        picks: List[str] = []
        for c in chunks:
            for s in c.text.split(". "):
                if any(t in s.lower() for t in terms):
                    cite = f"[{Path(c.source).name} • {c.chunk_id} • p{c.page_number}]"
                    picks.append(s.strip()+". "+cite)
        return " ".join(picks[:4]) or "I don't know based on the provided corpus."

    async def answer(self, query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self._should_idk(results):
            return {"answer":"I don't know based on the provided corpus.","citations":[],"confidence":0.0,"reason":"retrieval_low_confidence"}

        chunks = [r["chunk"] for r in results]
        text = None
        if self.has_openai and self.client:
            try:
                system = "Answer ONLY from the provided context. Use inline citations [file • chunk_id • p#]. If not in context, say you don't know."
                ctx = self._fmt_ctx(chunks)
                prompt = f"Question: {query}\n\nContext:\n{ctx}\n\nAnswer in 3–6 sentences with citations."
                resp = self.client.chat.completions.create(  # type: ignore
                    model="gpt-4o-mini",
                    temperature=0.1,
                    messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
                )
                text = resp.choices[0].message.content  # type: ignore
            except Exception as e:
                print({"warning":"generation_fallback_to_extractive","reason":type(e).__name__})
                text = None

        if not text:
            text = self._extractive(query, chunks)

        conf = float(max(r["score"] for r in results))
        return {"answer": text, "citations": self._citations(chunks), "confidence": conf, "reason": "ok"}
