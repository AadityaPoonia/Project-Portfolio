# Legal Judgment Analysis with Fine-Tuned LLMs

An MSc dissertation project that autonomously generates detailed legal analysis and predicts case verdicts for cases under India's **Negotiable Instruments Act, 1881 (NIA)** — combining fine-tuned domain LLMs with retrieval-augmented generation over case precedents.

MSc Data Science dissertation, University of Glasgow.

## The Problem

Legal analysis is expensive, slow, and bottlenecked on expert time. A general-purpose LLM asked to analyse an NIA case will produce fluent text, but it has no grounding in the statute or in the precedents that actually decide the outcome — it invents citations and misses the reasoning that matters. The question this project asks: **can a domain-adapted LLM with precedent retrieval close that gap?**

## Approach

**Model comparison** — evaluated LLaMA-3, Mistral 8x7B, and SaulLM-7B (a legal-domain model) on the same corpus, with and without retrieved context, to separate the gain from domain pretraining from the gain from retrieval.

**Fine-tuning** — SaulLM-7B adapted with **LoRA** (Low-Rank Adaptation), training a small set of adapter parameters rather than the full model, which made the fine-tune feasible under academic compute constraints.

**Retrieval-augmented generation** — case precedents are embedded and indexed with **FAISS**; for each new case, semantically similar prior judgments and the relevant statutory citations are retrieved and injected into the model's context.

**Prompt optimisation** — the **DSPy** framework optimises the prompt structure systematically rather than by hand, treating the prompt as a learnable component of the pipeline.

**Evaluation** — automated metrics (BERTScore, ROUGE, METEOR) alongside manual evaluation by a legal team, on the grounds that surface-level overlap metrics alone cannot tell you whether legal reasoning is *correct*.

## Results

**Mistral 8x7B with retrieved context** delivered the best overall performance — a notable finding, since it means retrieval-supplied context outweighed legal-domain pretraining on this task. The fine-tuned **SaulLM-7B** showed promising results despite operating under tight resource constraints, and remains the more compelling direction given better compute: handling longer legal texts and fine-tuning with more resources were the two limits that most constrained it.

## Repository Contents

| Notebook | Purpose |
|---|---|
| [`preprocessing.ipynb`](./preprocessing.ipynb) | Cleans and structures raw NIA case data into `cleaned_nia_cases.json` |
| [`prompting_using_dspy.ipynb`](./prompting_using_dspy.ipynb) | DSPy-based prompt generation and optimisation |
| [`inferencing.ipynb`](./inferencing.ipynb) | Generates and evaluates case analyses via Together AI |
| [`fine_tuning.ipynb`](./fine_tuning.ipynb) | LoRA fine-tuning of SaulLM-7B on the legal corpus |

| Directory | Contents |
|---|---|
| `data/` | Dataset files and the NIA statute text |
| `prompts/` | Prompt templates (with context, without context, DSPy) |
| `results/` | Generated analyses and optimised prompts from the inference runs |
| `fine_tuned_model_v2/` | LoRA adapter config and tokenizer files for the fine-tuned SaulLM-7B |

**Execution order:** `preprocessing` → `prompting_using_dspy` → `inferencing` → `fine_tuning`

## Data Availability

> **Note:** The main dataset file, `cases.nia_cases.json`, is **not included** in this repository due to its size and confidentiality constraints. If you need access for research or replication purposes, please [get in touch](mailto:aadityapoonia81@gmail.com) and I'll be happy to share it.
>
> `cleaned_nia_cases.json` is not present in `data/` initially either — it is generated automatically by running `preprocessing.ipynb` against the main dataset.

## Tech Stack

Python, PyTorch, SaulLM-7B, Mistral 8x7B, LLaMA-3, LoRA (PEFT), FAISS, Sentence Transformers, DSPy, Together AI, BERTScore / ROUGE / METEOR
