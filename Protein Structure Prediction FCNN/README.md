# Protein Secondary Structure Prediction with a Fully Convolutional Network

A fully convolutional neural network (FCNN) that predicts secondary protein structure directly from amino acid sequence data and position-specific scoring matrix (PSSM) profiles.

Built as part of the Deep Learning course in the MSc Data Science programme at the University of Glasgow (2023–24).

## Problem

Given a protein's amino acid sequence, predict the secondary structure label at every residue position. Because the output is a label *per position* rather than one label per sequence, the task is framed as dense sequence labelling — which is what makes a fully convolutional architecture a natural fit: it preserves sequence length end to end and predicts every position in a single forward pass.

## Approach

- **Input features** — amino acid sequences paired with their PSSM profiles, which encode evolutionary conservation at each residue and carry far more signal than the raw sequence alone.
- **Architecture** — a fully convolutional network with stacked 1D convolutional layers. Convolutions capture the local structural motifs (helices, sheets) that depend on a residue's immediate neighbourhood, while the absence of dense layers keeps the model length-agnostic.
- **Training** — cross-entropy loss with the Adam optimiser, batched through PyTorch `DataLoader`.
- **Evaluation** — per-residue accuracy and loss curves on a held-out test split, checking robustness on unseen sequences.

## Repository Contents

| File | Description |
|---|---|
| [`protein_structure_fcnn.ipynb`](./protein_structure_fcnn.ipynb) | Full pipeline — preprocessing, model definition, training loop, and evaluation |
| `seqs_train.csv` / `labels_train.csv` | Training sequences and their secondary structure labels |
| `seqs_test.csv` | Held-out test sequences |
| `sample.csv` | Sample submission format |

## Tech Stack

Python, PyTorch, pandas, NumPy, Matplotlib
