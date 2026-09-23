# Load-Shedding & Weather Pipeline

A real-world data engineering pipeline that ingests South African load-shedding
data (EskomSePush) and weather data (Open-Meteo), validates and transforms
both with Python, joins them by timestamp/area, and loads the result into a
queryable analytical store and then orchestrated end-to-end with Apache Airflow and
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
                 │  (Python)           │        │  (Python)            │
                 │  - schema checks    │        │  - range checks      │
                 │  - dedup / nulls    │        │  - timestamp gaps    │
                 │  - freshness check  │        │  - freshness check   │
                 └──────────┬──────────┘        └────────────┬─────────┘
                            └───────────────┬────────────────┘
                                            ▼
                                 ┌─────────────────────────┐
                                 │    join_enrich          │
                                 │  (Python)               │
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
- **Processing:** Python
- **Storage:** PostgreSQL (operational) — DuckDB under evaluation for the
  analytical layer, see `docs/decisions.md`
- **Sources:** EskomSePush API, Open-Meteo API
- **Tests:** pytest, focused on validation/transform logic

## Project layout

```
dags/               Airflow DAG definitions
src/ingestion/       Raw data pull tasks (one module per source)
src/transform/        Validation & transform logic
src/load/            Load-to-store logic
tests/               pytest suite for transform/validation
docs/                Architecture notes, design decisions, data dictionary
```

## Setup

### 1. Clone and enter the repo

```bash
git clone https://github.com/2308GJM/loadshedding-pipeline.git
cd loadshedding-pipeline
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `ESP_API_TOKEN` — get a free token at https://eskomsepush.gumroad.com/l/api
- `ESP_AREA_IDS` — find yours by searching `/areas_search?text=<suburb>` against
  the EskomSePush API (see comments in `.env.example`)

Leave `ESP_SCHEDULE_TEST_MODE=current` set — this uses EskomSePush's official
test facility to return a realistic sample outage event without consuming API
quota, which is necessary while national load-shedding stage is 0.

### 3. Create a virtual environment (for local runs outside Docker)

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# or: source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

## Running the pipeline locally (outside Docker)

Run each stage in order. Every module defaults to today's date.

```bash
# 1. Ingestion — pulls from both APIs, lands raw JSON
python src/ingestion/ingest_loadshedding.py
python src/ingestion/ingest_weather.py

# 2. Validation — cleans and flags each source
python src/transform/validate_transform_loadshedding.py
python src/transform/validate_transform_weather.py

# 3. Join — matches events to weather by nearest timestamp
python src/transform/join_enrich.py
```

The load step needs Postgres reachable. Start just the database (no need for
the full Airflow stack) and point at its host-mapped port:

```bash
docker compose up -d pipeline-db
PIPELINE_DB_HOST=localhost PIPELINE_DB_PORT=5433 python src/load/load_to_store.py
```

### Run the analysis

```bash
PIPELINE_DB_HOST=localhost PIPELINE_DB_PORT=5433 python src/analysis/analyze_events.py
```

## Running the full pipeline via Airflow (Docker)

```bash
docker compose up airflow-init
docker compose up
```

Airflow UI: http://localhost:8080 (login: `admin` / `admin`)

In the UI:
1. Unpause `loadshedding_weather_pipeline`
2. Click the ▶ trigger button to run it manually, or let it run on its
   `@daily` schedule
3. Click into the run to watch the graph view — all 6 tasks should turn green

To bring the stack down:
```bash
docker compose down
```

## Running tests

```bash
pytest tests/ -v
```

## Checking the data directly

```bash
docker exec -it loadshedding-pipeline-pipeline-db-1 psql -U pipeline -d loadshedding \
  -c "SELECT execution_date, schedule_id, stage, temperature_2m FROM enriched_events ORDER BY execution_date;"
```
## Status

Complete — ingestion, validation, join, and load are all implemented,
tested, and verified end-to-end via an automated Airflow DAG run. See
`docs/decisions.md` for design reasoning and known limitations, and
`docs/analysis.md` for findings. Built solo as part of the WeThinkCode
Data Engineering elective.

## Demo

Demo video: _link added on submission_

## Background

Author previously completed the ALX Data Engineering programme (Big Data
Fundamentals, Docker, Airflow, Apache Spark) — this project applies that
foundation to a self-directed, real-world dataset end to end.
