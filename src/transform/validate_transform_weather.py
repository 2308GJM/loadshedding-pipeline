"""
Validate and transform raw weather JSON into a clean, typed record set.

Design contract (see docs/decisions.md):
  - temperature_2m must be within a sane range for Johannesburg (-5 to 45 C)
  - timestamps must be hourly and contiguous for the fetched window;
    gaps are flagged, not silently interpolated
  - records with a fetched_at older than FRESHNESS_THRESHOLD are flagged
"""
from datetime import timedelta
from typing import Any

FRESHNESS_THRESHOLD = timedelta(hours=3)
SANE_TEMP_RANGE = (-5, 45)


def validate_record(record: dict[str, Any]) -> list[str]:
    problems = []

    temp = record.get("temperature_2m")
    if temp is None or not (SANE_TEMP_RANGE[0] <= temp <= SANE_TEMP_RANGE[1]):
        problems.append(f"temperature out of sane range: {temp!r}")

    if not record.get("time"):
        problems.append("time missing")

    return problems


def run(execution_date: str):
    """
    Loads raw JSON landed by src/ingestion/ingest_weather.py for
    execution_date, applies validate_record, checks hourly continuity,
    and writes clean output to the silver layer.
    """
    raise NotImplementedError("Wire up raw-file loading + Spark transform here")
