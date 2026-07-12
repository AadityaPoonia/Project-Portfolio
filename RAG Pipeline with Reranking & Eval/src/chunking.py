from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from .config import CFG

@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    source: str
    metadata: Dict[str, Any]
    page_number: Optional[int] = None

def _slug_from_source(source: str) -> str:
    s = Path(source).name.lower()
    if "diamond" in s or "acres" in s:
        return "acres_of_diamonds"
    if "science" in s and ("rich" in s or "getting" in s):
        return "science_of_getting_rich"
    if "barnum" in s or "money" in s:
        return "art_of_money_getting"
    if "smiles" in s or "self" in s:
        return "self_help"
    stem = Path(source).stem.lower().replace("-", "_").replace(" ", "_")
    return "".join(c if c.isalnum() or c == "_" else "_" for c in stem)

class DocumentChunker:
    """Paragraph-aware chunker with overlap; global per-book IDs {slug}_chunk_{i}."""
    def __init__(self, chunk_size: int = CFG.chunk_size, chunk_overlap: int = CFG.chunk_overlap):
        assert chunk_size > 100 and chunk_overlap < chunk_size
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _pack(self, text: str) -> List[str]:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()] or [text]
        chunks: List[str] = []
        buf = ""
        for p in paras:
            if len(p) > self.chunk_size:
                step = max(1, self.chunk_size - self.chunk_overlap)
                for i in range(0, len(p), step):
                    chunks.append(p[i : i + self.chunk_size])
                continue
            if len(buf) + len(p) + 2 <= self.chunk_size:
                buf = f"{buf}\n\n{p}" if buf else p
            else:
                if buf: chunks.append(buf)
                if chunks:
                    tail = chunks[-1][-self.chunk_overlap :]
                    buf = f"{tail}\n\n{p}"
                else:
                    buf = p
        if buf: chunks.append(buf)
        return chunks

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[DocumentChunk]:
        out: List[DocumentChunk] = []
        by_src: Dict[str, List[Dict[str, Any]]] = {}
        for d in documents: by_src.setdefault(d["source"], []).append(d)
        for src, pages in by_src.items():
            pages.sort(key=lambda x: (x.get("page_number") or 0))
            slug, counter = _slug_from_source(src), 0
            for page in pages:
                for text in self._pack(page["text"]):
                    cid = f"{slug}_chunk_{counter}"; counter += 1
                    out.append(DocumentChunk(
                        chunk_id=cid, text=text, source=src,
                        metadata=page.get("metadata", {}), page_number=page.get("page_number")
                    ))
        return out
