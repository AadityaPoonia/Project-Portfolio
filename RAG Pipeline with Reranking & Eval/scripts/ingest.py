# FILE: scripts/ingest.py  (replace whole file)
#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure project root on sys.path when running from scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
from src.pipeline import RAGPipeline, read_corpus_dir

async def main():
    import argparse
    ap = argparse.ArgumentParser(description="Ingest a corpus directory")
    ap.add_argument("input", nargs="?", default="data/raw", help="corpus folder (default: data/raw)")
    args = ap.parse_args()

    pipe = RAGPipeline()
    docs = read_corpus_dir(Path(args.input))
    await pipe.ingest_documents(docs)
    print({"ingested": True, "chunks": len(pipe.chunks)})

if __name__ == "__main__":
    asyncio.run(main())
