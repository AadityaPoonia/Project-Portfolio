from __future__ import annotations
import math
from typing import Any, Dict, List
from .config import CFG

try:
    from rank_bm25 import BM25Okapi
except Exception:
    BM25Okapi = None  # type: ignore

try:
    from sentence_transformers import CrossEncoder
except Exception:
    CrossEncoder = None  # type: ignore

def _norm(xs: List[float]) -> List[float]:
    if not xs: return xs
    lo, hi = min(xs), max(xs)
    if math.isclose(hi, lo): return [0.0 for _ in xs]
    return [(x - lo) / (hi - lo) for x in xs]

def _tok(s: str) -> List[str]:
    return [t for t in s.lower().split() if t]

class Reranker:
    """BM25 + Cross-Encoder fusion with weights. Disabled if deps missing or env off."""
    def __init__(self):
        self.enabled = CFG.rerank_enabled and (BM25Okapi is not None)
        self.has_ce = False; self.ce = None
        if self.enabled and CrossEncoder is not None:
            try:
                self.ce = CrossEncoder(CFG.rerank_model); self.has_ce = True
            except Exception:
                self.has_ce = False

    def bm25(self, query: str, passages: List[str]) -> List[float]:
        if not self.enabled or BM25Okapi is None: return [0.0]*len(passages)
        bm = BM25Okapi([_tok(p) for p in passages])
        return _norm(bm.get_scores(_tok(query)).tolist())

    def cross(self, query: str, passages: List[str]) -> List[float]:
        if not (self.enabled and self.has_ce and self.ce is not None): return [0.0]*len(passages)
        return _norm(self.ce.predict([(query,p) for p in passages]).tolist())

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        if not self.enabled: return candidates[:top_k]
        passages = [c["chunk"].text for c in candidates]
        s_vec = _norm([c["score"] for c in candidates])
        s_bm, s_ce = self.bm25(query, passages), self.cross(query, passages)
        ce_w, vec_w, bm_w = CFG.ce_w, CFG.vec_w, CFG.bm25_w
        if not self.has_ce:
            total = vec_w + bm_w; vec_w, bm_w = vec_w/total, bm_w/total; ce_w = 0.0
        fused = [ce_w*a + vec_w*b + bm_w*c for a,b,c in zip(s_ce, s_vec, s_bm)]
        order = sorted(range(len(candidates)), key=lambda i: fused[i], reverse=True)
        return [ {"chunk": candidates[i]["chunk"], "score": float(fused[i])} for i in order[:top_k] ]
