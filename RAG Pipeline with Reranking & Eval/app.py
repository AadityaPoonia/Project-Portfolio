#!/usr/bin/env python3
import asyncio, argparse, json
from src.pipeline import RAGPipeline, EvaluationHarness, read_corpus_dir

async def main():
    ap = argparse.ArgumentParser(description="RAG Q&A App (Python)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_ing = sub.add_parser("ingest"); p_ing.add_argument("input")
    p_ask = sub.add_parser("ask"); p_ask.add_argument("question"); p_ask.add_argument("--k", type=int, default=4)
    p_eval = sub.add_parser("evaluate"); p_eval.add_argument("questions"); p_eval.add_argument("--k", type=int, default=4)
    args = ap.parse_args()

    pipe = RAGPipeline()
    if args.cmd == "ingest":
        docs = read_corpus_dir(args.input); await pipe.ingest_documents(docs)
        print({"ingested": True, "chunks": len(pipe.chunks)})
    elif args.cmd == "ask":
        resp = await pipe.answer_question(args.question, top_k=args.k)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    elif args.cmd == "evaluate":
        ev = EvaluationHarness(pipe); await ev.load_questions(args.questions)
        report = await ev.run_evaluation(top_k=args.k)
        print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
