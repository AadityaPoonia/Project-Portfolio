from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
from .config import CFG
from .chunking import DocumentChunk, DocumentChunker
from .index import VectorIndex
from .reranker import Reranker
from .generator import AnswerGenerator

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None  # type: ignore

def read_pdf(path: str | Path) -> List[Dict[str, Any]]:
    if PdfReader is None:
        raise RuntimeError("pypdf is required to parse PDFs.")
    reader = PdfReader(str(path))
    out: List[Dict[str, Any]] = []
    for i, p in enumerate(reader.pages, start=1):
        try: txt = p.extract_text() or ""
        except Exception: txt = ""
        out.append({"text": txt, "source": str(path), "page_number": i, "metadata": {"filetype": "pdf"}})
    return out

def read_txt(path: str | Path) -> List[Dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return [{"text": text, "source": str(path), "page_number": None, "metadata": {"filetype": "txt"}}]

def read_corpus_dir(input_dir: str | Path) -> List[Dict[str, Any]]:
    d = Path(input_dir); docs: List[Dict[str, Any]] = []
    for p in sorted(d.glob("**/*")):
        if p.is_dir(): continue
        ext = p.suffix.lower()
        if ext == ".pdf": docs.extend(read_pdf(p))
        elif ext in {".txt", ".md"}: docs.extend(read_txt(p))
    return docs

class RAGPipeline:
    def __init__(self):
        self.chunker = DocumentChunker()
        self.index = VectorIndex()
        self.reranker = Reranker()
        self.generator = AnswerGenerator()
        self.chunks: List[DocumentChunk] = []
        self.index.load()

    async def ingest_documents(self, documents: List[Dict[str, Any]]) -> bool:
        self.chunks = self.chunker.chunk_documents(documents)
        await self.index.create_index(self.chunks)
        return True

    async def answer_question(self, query: str, top_k: int = CFG.top_k) -> Dict[str, Any]:
        cand_k = max(top_k * 5, CFG.rerank_top_n) if self.reranker.enabled else top_k
        initial = await self.index.search(query, top_k=cand_k)
        reranked = self.reranker.rerank(query, initial, top_k) if self.reranker.enabled else initial[:top_k]
        ans = await self.generator.answer(query, reranked)
        return {
            "query": query,
            "results": [
                {"chunk_id": r["chunk"].chunk_id, "score": r["score"], "source": Path(r["chunk"].source).name, "page_number": r["chunk"].page_number}
                for r in reranked
            ],
            **ans,
        }

class EvaluationHarness:
    def __init__(self, rag_pipeline: RAGPipeline):
        self.rag_pipeline = rag_pipeline
        self.questions: List[Dict[str, Any]] = []

    async def load_questions(self, questions_file: str) -> bool:
        data = json.loads(Path(questions_file).read_text(encoding="utf-8"))
        assert isinstance(data, list) and data, "questions.json must be a non-empty list"
        self.questions = data; return True

    async def run_evaluation(self, top_k: int = CFG.top_k) -> Dict[str, Any]:
        assert self.questions, "Load questions first"
        results: List[Dict[str, Any]] = []
        for q in self.questions:
            query = q["question"]; expected = set(q.get("expected_references", []))
            resp = await self.rag_pipeline.answer_question(query, top_k=top_k)
            cited = {c["chunk_id"] for c in resp.get("citations", [])} | {r["chunk_id"] for r in resp.get("results", [])}
            matched = bool(expected & cited)
            results.append({
                "question": query, "category": q.get("category"),
                "answer": resp.get("answer"), "citations": resp.get("citations"),
                "top_results": resp.get("results"), "expected": list(expected),
                "matched_any_expected": matched, "confidence": resp.get("confidence"),
            })
        return self._report(results)

    @staticmethod
    def _report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(results); hit = sum(1 for r in results if r["matched_any_expected"]) if results else 0
        return {"total_questions": total, "hit_at_k_any": hit, "hit@k_rate": (hit/total) if total else 0.0, "details": results}
