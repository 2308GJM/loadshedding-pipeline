# Design decisions

This file exists so every non-obvious choice in this pipeline has a written
reason. Update it as decisions change — a changed decision with no note is
a red flag, not a shortcut.

## Why two sources instead of one

A single-source pipeline (just load-shedding data) is a schedule lookup, not
an engineering problem. Adding weather data forces a real join across two
sources with different update cadences: load-shedding schedules change
irregularly and reactively, weather updates on a predictable interval. That
mismatch is the actual engineering problem this project solves.

## Why land raw data before transforming it

Bronze/silver/gold layering: raw API responses are stored untouched and
timestamped before any parsing happens. If a transform bug is discovered
later, the raw layer means reprocessing from source instead of re-fetching
(or losing) historical data. This also makes freshness/staleness auditing
possible after the fact.

## Why PySpark instead of pandas

Data volume here is small enough that pandas would work. Spark is used
because the validation/transform logic (schema enforcement, dedup, range
checks) is written once and should scale unchanged whether the pipeline is
processing a week of data or a year. It's also a deliberate extension of
ALX coursework (Apache Spark, Big Data Fundamentals) into a real pipeline
rather than a training exercise.

## Why Airflow instead of a cron script

A cron script has no visibility into partial failure, no retry semantics,
and no dependency graph. Airflow makes the pipeline's structure explicit:
which tasks can run in parallel (the two ingestion tasks), which must wait
on both (the join), and what happens on failure (retry policy, alerting).
This is also directly reusable for the Cloud Computing elective work if
pursued later.

## Join strategy: nearest-timestamp with a tolerance window

Load-shedding events and weather readings will rarely share an exact
timestamp. The join uses nearest-available weather reading within a defined
tolerance window (documented in `src/transform/join_enrich.py` once
implemented). Outage windows with no weather reading inside the tolerance
are logged and excluded from the enriched dataset, not silently joined to
whatever is closest regardless of distance.

## Storage: Postgres vs DuckDB

Postgres is used as the operational serving layer written to by the
pipeline — it's the standard choice for a service-backed store, runs
cleanly as its own Docker Compose service, and pairs naturally with cloud
deployment (RDS) if this pipeline is ever hosted. DuckDB is being evaluated
as an embedded analytical layer for the final insight/analysis step, since
it's built for exactly that kind of query workload. Final call recorded
here once the analysis layer is built.

## What "data quality" means in this pipeline, concretely

- Schema enforcement before any transform runs
- Explicit range checks (e.g. load-shedding stage must be 0–8)
- Explicit freshness checks — data older than an expected threshold is
  flagged, not silently used
- Failures are logged with enough context to debug, not swallowed
