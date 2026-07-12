# Distributed Text Search & Ranking with Apache Spark

A batch text search and filtering pipeline built on Apache Spark that ranks a ~5 GB news corpus against user queries using the **DPH** retrieval model, then removes near-duplicate results to return a diverse top-10 per query.

Built for the Big Data course in the MSc Data Science programme at the University of Glasgow (2023–24).

## Results

**Full ~5 GB dataset, 10 queries, 4 local executors → ~120 seconds end to end.**

Hitting that number was the real work of the project. The naive implementation shuffles the entire corpus per query; the delivered pipeline restructures the job so that term statistics are computed once and reused across queries, keeping the expensive passes over the corpus to a minimum.

## The Pipeline

1. **Text preprocessing** — stopword removal and stemming on both documents and queries, so that term mismatch (`running` vs. `run`) doesn't cost a relevant document its rank.
2. **Term frequency computation** — a flat-map over the corpus producing per-term frequencies, reduced into the corpus-wide statistics the ranking model needs.
3. **DPH ranking** — each document is scored against each query with the DPH model, a parameter-free divergence-from-randomness ranker.
4. **Redundancy filtering** — the ranked list is scanned for near-duplicates: when any two documents have a title similarity below the 0.5 threshold, only the higher-DPH-scoring one survives. Filtering happens *after* ranking, and the pipeline back-fills from the remaining candidates so that a full 10 documents are still returned per query.

## Repository Structure

```text
BigData-AE/
├── src/uk/ac/gla/dcs/bigdata/
│   ├── apps/AssessedExercise.java        # Spark job entry point
│   ├── studentfunctions/                 # Custom map/flatMap/reduce functions
│   │   ├── NewsFlatMap.java              #   Document preprocessing
│   │   ├── FlatMapTermFrequency.java     #   Term frequency extraction
│   │   ├── FrequencyReduceGroups.java    #   Corpus statistics aggregation
│   │   ├── QueryScoreFormaterMap.java    #   DPH scoring
│   │   └── DocumentRankingMapGroup.java  #   Ranking + redundancy filtering
│   ├── studentstructures/                # Custom serializable data structures
│   └── provided*/                        # Provided scorers, structures, utilities
├── data/queries.list                     # Query set
└── pom.xml                               # Maven build
```

## Tech Stack

Apache Spark, Java, Maven

## Dataset

The full corpus (TREC Washington Post collection, ~5 GB) is too large to include here. It is available from [ir-datasets](https://ir-datasets.com/wapo.html). A small example file is included under `data/` for reference.
