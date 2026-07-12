# FILE: scripts/eval.py  (replace whole file)
#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure project root on sys.path when running from scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
import json
from src.pipeline import RAGPipeline, EvaluationHarness, read_corpus_dir

async def main():
    import argparse
    ap = argparse.ArgumentParser(description="Run mini evaluation (ingest → evaluate)")
    ap.add_argument("questions", nargs="?", default="questions.json", help="questions file (default: questions.json)")
    ap.add_argument("--k", type=int, default=4, help="top-k")
    ap.add_argument("--data", default="data/raw", help="corpus folder (default: data/raw)")
    args = ap.parse_args()

    pipe = RAGPipeline()
    # Ingest so this script works standalone
    docs = read_corpus_dir(Path(args.data))
    await pipe.ingest_documents(docs)

    ev = EvaluationHarness(pipe)
    await ev.load_questions(args.questions)
    report = await ev.run_evaluation(top_k=args.k)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
