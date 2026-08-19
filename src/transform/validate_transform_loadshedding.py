"""
Validate and transform raw load-shedding JSON into a clean, typed record set.

Design contract (see docs/decisions.md):
  - stage must be an integer in range 0-8
  - area_id must be non-null and non-empty
  - records with a fetched_at older than FRESHNESS_THRESHOLD are flagged,
    not silently dropped
  - duplicate (area_id, start_time) pairs are deduplicated, keeping the
    most recently fetched record

This module is intentionally the first target for pytest coverage — the
validation rules are the part of this pipeline most worth testing, since
a silent data quality bug here would quietly corrupt the join and every
downstream insight.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

FRESHNESS_THRESHOLD = timedelta(hours=6)
VALID_STAGE_RANGE = range(0, 9)  # 0-8 inclusive


class ValidationError(Exception):
    pass


def validate_record(record: dict[str, Any]) -> list[str]:
    """Return a list of validation problems for a single record (empty = valid)."""
    problems = []

    stage = record.get("stage")
    if stage is None or int(stage) not in VALID_STAGE_RANGE:
        problems.append(f"stage out of range or missing: {stage!r}")

    area_id = record.get("area_id")
    if not area_id:
        problems.append("area_id missing or empty")

    fetched_at = record.get("fetched_at")
    if fetched_at:
        fetched_dt = datetime.fromisoformat(fetched_at)
        if datetime.now(timezone.utc) - fetched_dt > FRESHNESS_THRESHOLD:
            problems.append(f"stale record, fetched_at={fetched_at}")
    else:
        problems.append("fetched_at missing")

    return problems


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the most recently fetched record per (area_id, start_time)."""
    latest: dict[tuple, dict[str, Any]] = {}
    for record in records:
        key = (record.get("area_id"), record.get("start_time"))
        existing = latest.get(key)
        if existing is None or record["fetched_at"] > existing["fetched_at"]:
            latest[key] = record
    return list(latest.values())


def run(execution_date: str):
    """
    Loads raw JSON landed by src/ingestion/ingest_loadshedding.py for
    execution_date, applies validate_record + deduplicate, and writes the
    clean output to the silver layer.

    NOTE: PySpark wiring for this at real volume is the next implementation
    step — this module currently defines and tests the validation contract
    in plain Python so the logic can be unit tested fast, then lifted into
    a Spark UDF/DataFrame operation without changing the rules themselves.
    """
    raise NotImplementedError("Wire up raw-file loading + Spark transform here")
