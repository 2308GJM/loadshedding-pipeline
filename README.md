# Load-Shedding & Weather Pipeline

A real-world data engineering pipeline that ingests South African load-shedding
data (EskomSePush) and weather data (Open-Meteo), validates and transforms
both with PySpark, joins them by timestamp/area, and loads the result into a
queryable analytical store — orchestrated end-to-end with Apache Airflow and
containerized with Docker Compose.

**Question this pipeline answers:** does load-shedding stage or outage
duration correlate with weather conditions, time of day, or day of week?

## Why this project

Two sources with different update cadences, a genuine join problem (nearest-
timestamp matching, missing weather for a given outage window), explicit
data quality enforcement, and a real orchestrated DAG rather than a single
script. Every layer below is a deliberate design decision — see
[`docs/decisions.md`](docs/decisions.md) for the reasoning behind each one.

## Architecture

```
                 ┌─────────────────────┐        ┌──────────────────────┐
                 │ ingest_loadshedding │        │   ingest_weather     │
                 │ (EskomSePush API)   │        │  (Open-Meteo API)    │
                 └──────────┬──────────┘        └────────────┬─────────┘
                            │  raw JSON, landed as-is        │
                            ▼                                ▼
                 ┌─────────────────────┐        ┌──────────────────────┐
                 │ validate_transform  │        │ validate_transform   │
                 │  (PySpark)          │        │  (PySpark)           │
                 │  - schema checks    │        │  - range checks      │
                 │  - dedup / nulls    │        │  - timestamp gaps    │
                 │  - freshness check  │        │  - freshness check   │
                 └──────────┬──────────┘        └────────────┬─────────┘
                            └───────────────┬────────────────┘
                                            ▼
                                 ┌─────────────────────────┐
                                 │    join_enrich          │
                                 │  (PySpark)              │
                                 │  nearest-timestamp      │
                                 │  join, tolerance window │
                                 └──────────┬──────────────┘
                                            ▼
                                 ┌──────────────────────┐
                                 │    load_to_store     │
                                 │  (Postgres / DuckDB) │
                                 └──────────┬───────────┘
                                            ▼
                                 ┌──────────────────────┐
                                 │  analysis / insight  │
                                 │  (notebook/dashboard)│
                                 └──────────────────────┘
```

All orchestrated by a single Airflow DAG: `dags/loadshedding_pipeline.py`.

## Stack

- **Orchestration:** Apache Airflow (Docker)
- **Processing:** PySpark
- **Storage:** PostgreSQL (operational) — DuckDB under evaluation for the
  analytical layer, see `docs/decisions.md`
- **Sources:** EskomSePush API, Open-Meteo API
- **Tests:** pytest, focused on validation/transform logic

## Project layout

```
dags/               Airflow DAG definitions
src/ingestion/       Raw data pull tasks (one module per source)
src/transform/        PySpark validation & transform logic
src/load/            Load-to-store logic
tests/               pytest suite for transform/validation
docs/                Architecture notes, design decisions, data dictionary
```

## Running it

```bash
docker compose up
```

Airflow UI: http://localhost:8080

## Status

🚧 In active development — see commit history for progress. Built solo as
part of the WeThinkCode Data Engineering elective.

## Demo

Demo video: _link added on submission_

## Background

Author previously completed the ALX Data Engineering programme (Big Data
Fundamentals, Docker, Airflow, Apache Spark) — this project applies that
foundation to a self-directed, real-world dataset end to end.
