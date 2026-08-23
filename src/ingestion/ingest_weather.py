"""
Validate and transform raw weather JSON into a clean, typed record set.

SCHEMA NOTE (confirmed 23 Aug 2026 against real landed data): Open-Meteo
returns hourly data as PARALLEL ARRAYS under payload.hourly — time[],
temperature_2m[], precipitation[], weather_code[] — all indexed together,
not a list of per-hour records. flatten_hourly_weather() below zips these
into flat per-hour records; validate_record() then operates on those flat
records exactly as originally designed (its field names — temperature_2m,
time — turned out to match the real API correctly).

Design contract (see docs/decisions.md):
  - temperature_2m must be within a sane range for Johannesburg (-5 to 45 C)
  - time must be present
  - records with a fetched_at older than FRESHNESS_THRESHOLD are flagged
  - overlapping hours across consecutive daily fetches (past_days=1 means
    each run re-fetches part of the previous day) are deduplicated by time,
    keeping the most recently fetched record
"""
import glob
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

FRESHNESS_THRESHOLD = timedelta(hours=3)
SANE_TEMP_RANGE = (-5, 45)

RAW_DATA_DIR = os.environ.get("WEATHER_RAW_DATA_DIR", "data/raw/weather")
SILVER_DATA_DIR = os.environ.get("WEATHER_SILVER_DATA_DIR", "data/silver/weather")


def flatten_hourly_weather(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Zip payload.hourly's parallel arrays (time, temperature_2m,
    precipitation, weather_code) into one flat record per hour.
    """
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precip = hourly.get("precipitation", [])
    codes = hourly.get("weather_code", [])

    records = []
    for i, time in enumerate(times):
        records.append(
            {
                "time": time,
                "temperature_2m": temps[i] if i < len(temps) else None,
                "precipitation": precip[i] if i < len(precip) else None,
                "weather_code": codes[i] if i < len(codes) else None,
            }
        )
    return records


def validate_record(record: dict[str, Any]) -> list[str]:
    problems = []

    temp = record.get("temperature_2m")
    if temp is None or not (SANE_TEMP_RANGE[0] <= temp <= SANE_TEMP_RANGE[1]):
        problems.append(f"temperature out of sane range: {temp!r}")

    if not record.get("time"):
        problems.append("time missing")

    fetched_at = record.get("fetched_at")
    if fetched_at:
        fetched_dt = datetime.fromisoformat(fetched_at)
        if datetime.now(timezone.utc) - fetched_dt > FRESHNESS_THRESHOLD:
            problems.append(f"stale record, fetched_at={fetched_at}")
    else:
        problems.append("fetched_at missing")

    return problems


def deduplicate_by_time(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the most recently fetched record per hourly timestamp."""
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record.get("time")
        existing = latest.get(key)
        if existing is None or record["fetched_at"] > existing["fetched_at"]:
            latest[key] = record
    return list(latest.values())


def _load_json(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def run(execution_date: str):
    """
    Loads hourly.json landed under RAW_DATA_DIR/{execution_date}/,
    flattens the parallel-array hourly payload, validates and
    deduplicates by timestamp, and writes the result to the silver
    layer. Nothing is silently dropped — every record carries its
    validation_problems list (empty = valid).
    """
    day_dir = os.path.join(RAW_DATA_DIR, execution_date)

    all_records: list[dict[str, Any]] = []
    for hourly_path in glob.glob(os.path.join(day_dir, "hourly.json")):
        raw = _load_json(hourly_path)
        fetched_at = raw.get("fetched_at")
        payload = raw.get("payload", {})

        records = flatten_hourly_weather(payload)
        for record in records:
            record["fetched_at"] = fetched_at
        all_records.extend(records)

    deduped = deduplicate_by_time(all_records)
    for record in deduped:
        record["validation_problems"] = validate_record(record)

    out_dir = os.path.join(SILVER_DATA_DIR, execution_date)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "weather_hourly.json")
    with open(out_path, "w") as f:
        json.dump(deduped, f, indent=2)

    return out_path


if __name__ == "__main__":
    run(execution_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))