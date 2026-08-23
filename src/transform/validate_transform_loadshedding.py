"""
Validate and transform raw load-shedding JSON into a clean, typed record set.

SCHEMA NOTE (updated 23 Aug 2026 against real landed data): the raw
schedule_*.json files landed by src/ingestion/ingest_loadshedding.py contain
two very different things under payload:

  payload.events           -> real/upcoming outage events (start, end, note)
                               THIS is what this module processes.
  payload.schedule.days    -> the full theoretical weekly schedule for every
                               stage 1-8, whether or not that stage is
                               currently active. NOT processed here — joining
                               weather to every theoretical slot would
                               manufacture outages that never happened.

The stage number is embedded as free text in `note` (e.g.
"Stage 8 (TESTING: current)"), not a clean field, so it must be parsed out.

Design contract (see docs/decisions.md):
  - stage must be an integer in range 0-8
  - end must be after start
  - records with a fetched_at older than FRESHNESS_THRESHOLD are flagged,
    not silently dropped
  - duplicate (schedule_id, start, end) triples are deduplicated, keeping
    the most recently fetched record

"""

import glob
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

FRESHNESS_THRESHOLD = timedelta(hours=6)
VALID_STAGE_RANGE = range(0, 9)  # 0-8 inclusive

RAW_DATA_DIR = os.environ.get("RAW_DATA_DIR", "data/raw/loadshedding")
SILVER_DATA_DIR = os.environ.get("SILVER_DATA_DIR", "data/silver/loadshedding")

STAGE_PATTERN = re.compile(r"Stage\s*(\d+)", re.IGNORECASE)

class ValidationError(Exception):
    pass


class ValidationError(Exception):
    pass


def parse_stage_from_note(note: str) -> int | None:
    """Extract the integer stage number out of a free-text note like
    'Stage 8 (TESTING: current)'. Returns None if no stage number is found."""
    if not note:
        return None
    match = STAGE_PATTERN.search(note)
    if not match:
        return None
    return int(match.group(1))


def flatten_schedule_events(
        payload: dict[str, Any], schedule_id: str, area_id: str | None = None
) -> list[dict[str, Any]]:
    """
    Turn payload.events from one landed schedule_*.json file into flat
    records ready for validate_record(). Does NOT touch payload.schedule
    (the theoretical weekly grid) — see module docstring.
    """
    records = []
    for event in payload.get("events", []):
        note = event.get("note", "")
        records.append(
            {
                "schedule_id": schedule_id,
                "area_id": area_id,
                "stage": parse_stage_from_note(note),
                "note": note,
                "start": event.get("start"),
                "end": event.get("end"),
            }
        )
    return records


def validate_record(record: dict[str, Any]) -> list[str]:
    """Return a list of validation problems for a single record (empty = valid)."""
    problems = []

    stage = record.get("stage")
    if stage is None or stage not in VALID_STAGE_RANGE:
        problems.append(f"stage out of range or unparseable: {stage!r} (note={record.get('note')!r})")

    start = record.get("start")
    end = record.get("end")
    if not start:
        problems.append("start missing")
    if not end:
        problems.append("end missing")
    if start and end:
        try:
            if datetime.fromisoformat(end) <= datetime.fromisoformat(start):
                problems.append(f"end ({end}) is not after start ({start})")
        except ValueError:
            problems.append(f"start/end not valid ISO timestamps: start={start!r} end={end!r}")

    fetched_at = record.get("fetched_at")
    if fetched_at:
        fetched_dt = datetime.fromisoformat(fetched_at)
        if datetime.now(timezone.utc) - fetched_dt > FRESHNESS_THRESHOLD:
            problems.append(f"stale record, fetched_at={fetched_at}")
    else:
        problems.append("fetched_at missing")

    return problems


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the most recently fetched record per (schedule_id, start, end)."""
    latest: dict[tuple, dict[str, Any]] = {}
    for record in records:
        key = (record.get("schedule_id"), record.get("start"), record.get("end"))
        existing = latest.get(key)
        if existing is None or record["fetched_at"] > existing["fetched_at"]:
            latest[key] = record
    return list(latest.values())


def _load_json(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def run(execution_date: str):
    """
    Loads every area_*.json and schedule_*.json landed under
    RAW_DATA_DIR/{execution_date}/, flattens schedule events, validates
    and deduplicates them, and writes the result to the silver layer.
    Nothing is silently dropped — every record is written with its
    validation_problems list (empty list = valid) so downstream steps
    decide what to do with flagged records rather than losing them here.
    """
    day_dir = os.path.join(RAW_DATA_DIR, execution_date)

    schedule_to_area: dict[str, str] = {}
    for area_path in glob.glob(os.path.join(day_dir, "area_*.json")):
        area_raw = _load_json(area_path)
        area_payload = area_raw.get("payload", {})
        area_id = area_payload.get("id")
        for schedule in area_payload.get("schedules", []):
            sid = schedule.get("id")
            if sid:
                schedule_to_area[sid] = area_id

    all_records: list[dict[str, Any]] = []
    for schedule_path in glob.glob(os.path.join(day_dir, "schedule_*.json")):
        filename = os.path.basename(schedule_path)
        schedule_id = filename[len("schedule_"):-len(".json")]

        schedule_raw = _load_json(schedule_path)
        fetched_at = schedule_raw.get("fetched_at")
        payload = schedule_raw.get("payload", {})

        records = flatten_schedule_events(
            payload, schedule_id, area_id=schedule_to_area.get(schedule_id)
        )
        for record in records:
            record["fetched_at"] = fetched_at
        all_records.extend(records)

    deduped = deduplicate(all_records)
    for record in deduped:
        record["validation_problems"] = validate_record(record)

    out_dir = os.path.join(SILVER_DATA_DIR, execution_date)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "loadshedding_events.json")
    with open(out_path, "w") as f:
        json.dump(deduped, f, indent=2)

    return out_path


if __name__ == "__main__":
    run(execution_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))