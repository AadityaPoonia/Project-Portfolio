# Movie Analytics — Multiview Visualization Dashboards

Three distinct multiview visualization systems built over the TMDB movie dataset (~930k films), each exploring a different design approach to the same analytical question: **what drives a movie's commercial and critical success?**

Built with Altair and Vega-Lite as part of the Information Visualization course in the MSc Data Science programme at the University of Glasgow (2023–24).

## The Systems

Each system is a coordinated multiview dashboard with **brushing and linking** — selecting a range in one view filters every other view, so a user can trace a pattern (a genre, a budget band, a release era) across the full dataset without leaving the dashboard.

| Notebook | Focus |
|---|---|
| [`System A.ipynb`](./System%20A.ipynb) | First design iteration — coordinated views over genre, budget, revenue, and rating |
| [`System B.ipynb`](./System%20B.ipynb) | Alternative encoding and layout choices, targeting the same analytical tasks |
| [`System C.ipynb`](./System%20C.ipynb) | Extended system with geographic views and advanced generalized selection techniques |

Building three systems rather than one was deliberate: it allowed the design decisions (encoding choice, view layout, interaction model) to be **compared against each other** and evaluated with users, instead of asserted in isolation.

## Key Work

- Dataset selection, cleaning, and categorisation of the TMDB movie corpus.
- Implementation of three multiview systems with brushing and linking across all views.
- Extension of core interactions with generalized selection techniques.
- Comparative evaluation of design decisions through user testing, with documented findings and proposed improvements.

## Tech Stack

Python, Altair, Vega-Lite, pandas, GeoPandas (Natural Earth country boundaries)

## Dataset

[TMDB Movies Dataset 2023 — 930k Movies](https://www.kaggle.com/datasets/asaniczka/tmdb-movies-dataset-2023-930k-movies) (Kaggle)

## Reference Systems

- [Dashboard for a Movie Producer](https://www.dashboardy.pl/en/dashboard-for-movie-producer/)
- [Altair geoshape marks](https://altair-viz.github.io/user_guide/marks/geoshape.html)
