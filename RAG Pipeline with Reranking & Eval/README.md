# RAG Pipeline with Reranking & Evaluation

A compact Retrieval-Augmented Generation (RAG) system that ingests four classic books, builds a vector index, retrieves top‑k chunks, re‑ranks them with a BM25 + Cross‑Encoder fusion, and generates grounded answers with inline citations.

Three things distinguish it from a toy RAG demo:

- **Reranking that fuses three signals** — cross-encoder relevance, vector similarity, and BM25 lexical score, weighted and combined, rather than trusting embedding cosine similarity alone.
- **An "I don't know" policy** — the system refuses to answer when retrieval confidence is too low, instead of confabulating from weak chunks.
- **A built-in evaluation harness** — `questions.json` defines expected source chunks per question, and the harness reports **hit@k** on whether retrieval actually surfaced them.

It also runs **fully offline** (TF-IDF embeddings + extractive generation) when no OpenAI key is available.

## Quick start (VS Code — one click)

**Prereqs**
- **Node.js** (LTS)
- **Python 3.9+** with `pip`

**Place the data**
```
data/raw/
  AcresOfDiamonds.pdf
  p-t-barnum_art-of-money-getting.pdf
  science-of-getting-rich.pdf
  Smiles_0379.pdf
```

**Environment**
1) Copy `.env.example` → `.env`  
2) If you want online LLM features, set your key:
```
OPENAI_API_KEY=sk-...your-key...
```
3) Modes (can run fully offline):
```
USE_OPENAI_EMBEDDINGS=auto   # auto|true|false
USE_OPENAI_GENERATION=auto   # auto|true|false
```

**Install Python deps (once)**
```
pip install -r requirements.txt
```

**Run from VS Code (no terminal typing)**
- Open **Run and Debug** (▶️).
- Choose **Node: Run All (prompt & ask)** → type your question → it **ingests then answers**.
- Or choose **Node: Run All (evaluate)** → it **ingests then evaluates** `questions.json`.

> The Node entry (`app.js` / `runner.js`) calls the Python pipeline under the hood.

---

## What’s included

```
app.js               # Required Node entry; delegates to Python CLI
evaluate.js          # Keeps "npm run evaluate" working (delegates to Node entry)
runner.js            # One-click: ingest → ask / ingest → evaluate
app.py               # Python CLI: ingest | ask | evaluate
src/
  config.py          # .env loader & configuration
  chunking.py        # Paragraph-aware chunker; stable IDs {slug}_chunk_{n}
  index.py           # Vector index: OpenAI embeddings or TF-IDF fallback
  reranker.py        # BM25 + Cross-Encoder fusion (optional)
  generator.py       # Grounded answers + IDK policy + citations
  pipeline.py        # Orchestration + PDF/TXT readers + EvaluationHarness
scripts/
  ingest.py          # Tiny helper (optional) -> Ingest directly using python
  eval.py            # Tiny helper (optional) -> Evaluate directly using python
questions.json       # Mini evaluation set
.vscode/launch.json  # Run/Debug configs (Node “Run All” buttons)
.env.example         # Template (commit this)
requirements.txt     # Python dependencies
```

---

## Architecture overview

- **Ingestion & chunking**  
  PDFs are parsed page‑by‑page; paragraphs are packed into ~**1200**‑char chunks with **200** overlap.  
  Each book gets a canonical slug and **global** chunk IDs:
  - `AcresOfDiamonds.pdf` → `acres_of_diamonds_chunk_*`
  - `p-t-barnum_art-of-money-getting.pdf` → `art_of_money_getting_chunk_*`
  - `science-of-getting-rich.pdf` → `science_of_getting_rich_chunk_*`
  - `Smiles_0379.pdf` → `self_help_chunk_*`

- **Index & retrieval**  
  A vector index (L2‑normalized matrix) is persisted to `./.rag_index/`.  
  Embeddings: **OpenAI `text-embedding-3-small`** if allowed, else **TF‑IDF** fallback.  
  Retrieval uses cosine similarity; `TOP_K` is configurable (default 4).

- **Re‑ranking (optional)**  
  **BM25** lexical scores + **Cross‑Encoder** (`cross-encoder/ms-marco-MiniLM-L-6-v2`) fused with the initial vector score.  
  Weights (`RERANK_WEIGHTS=CE,Vector,BM25`) and toggles are set in `.env`.

- **Answer generation**  
  **OpenAI chat (`gpt-4o-mini`)** when enabled; otherwise an **extractive fallback** stitches sentences from retrieved chunks.  
  Inline citations: `[file • chunk_id • p#]`.

- **“I don’t know” policy**  
  Returns IDK if the top similarity is below `SIMILARITY_THRESHOLD` **or** fewer than two chunks exceed the threshold (defaults in `.env`).

- **Evaluation harness**  
  Loads `questions.json`; for each question runs retrieval → (optional) re‑rank → answer.  
  Prints retrieved chunk IDs, final answer, and whether any retrieved/cited chunk matches `expected_references`. Reports **hit@k(any)**.

---

## `questions.json` format

```json
[
  {
    "question": "What are the main principles of getting rich according to Wallace Wattles?",
    "expected_references": [
      "science_of_getting_rich_chunk_1",
      "science_of_getting_rich_chunk_5"
    ],
    "category": "principles"
  }
]
```

Used only for evaluation (not training). `expected_references` should use the stable chunk‑ID scheme above.

---

## Configuration reference (`.env`)

```ini
# Storage
INDEX_DIR=.rag_index

# Retrieval & thresholds
TOP_K=4
SIMILARITY_THRESHOLD=0.22

# Chunking
CHUNK_SIZE=1200
CHUNK_OVERLAP=200

# Re-ranking
RERANK_ENABLED=true
RERANK_TOP_N=20
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RERANK_WEIGHTS=0.6,0.25,0.15  # CE, Vector, BM25

# OpenAI (optional; keep offline if you want)
OPENAI_API_KEY=sk-...        # omit to run offline
USE_OPENAI_EMBEDDINGS=auto   # auto|true|false
USE_OPENAI_GENERATION=auto   # auto|true|false
```

**Typical offline setting (no credits / hit 429)**  
```
USE_OPENAI_GENERATION=false
```
Optionally:
```
USE_OPENAI_EMBEDDINGS=false
```

---

## Troubleshooting

- **429 / insufficient_quota**  
  Set `USE_OPENAI_GENERATION=false` to force extractive answers, or add credits to your OpenAI account.

- **“Index not built. Run ingest first.”**  
  Use **Node: Run All (prompt & ask)** or **Node: Run All (evaluate)** (they ingest automatically).

- **Missing PDFs**  
  Ensure the four files are present under `data/raw/` with the exact filenames above.

- **First‑time re‑ranker feels slow**  
  The Cross‑Encoder model is downloaded once. You can disable re‑ranking via `RERANK_ENABLED=false`.

- **PDF warnings like “Ignoring wrong pointing object …”**  
  Benign parsing warnings from some PDFs; safe to ignore.

---

## Runtime setup notes (Node & Python)

### Node.js on Windows (PATH or explicit path)
If VS Code can’t find Node, do one of the following:

**A) Add Node to PATH (recommended)**  
1. Win+R → `sysdm.cpl` → **Advanced** → **Environment Variables…**  
2. User variables → **Path** → **Edit** → **New** → add:  
   - `C:\\Program Files\\nodejs\\`  
   - *(optional)* `%AppData%\\npm`  
3. Close all dialogs with **OK**, then fully restart VS Code.

**B) Use explicit runtime in VS Code**  
In `.vscode/launch.json`, set:
```json
"runtimeExecutable": "C:\\Program Files\\nodejs\\node.exe"
```
This bypasses PATH entirely.

**Verify** in a new terminal: `node -v` and `where node`.

### Python runtime
Ensure Python 3.9+ is available on PATH as `python`, `python3`, or `py`. The Node entry (`app.js`) invokes the Python CLI under the hood.

---

## OpenAI online/offline modes

The app reads `.env` and automatically chooses between OpenAI and offline fallbacks.

```ini
# .env (see .env.example)
OPENAI_API_KEY=sk-...
USE_OPENAI_EMBEDDINGS=auto   # auto|true|false
USE_OPENAI_GENERATION=auto   # auto|true|false
```

- **Generation 429 / no credits?** Set `USE_OPENAI_GENERATION=false` to force extractive answers.  
- **No internet?** Set `USE_OPENAI_EMBEDDINGS=false` to force TF‑IDF embeddings.  
- When set to `auto`, OpenAI is used only if a key is present and calls succeed; otherwise the app transparently falls back and logs a warning.

These modes apply equally whether you run via the **Node Run All** buttons or the Python runners.

---