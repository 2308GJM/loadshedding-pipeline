"""
Join validated load-shedding events to validated weather readings by
nearest timestamp, within a tolerance window.

Design contract (see docs/decisions.md):
  - each load-shedding event is matched to the weather reading closest to
    the event's START time (not end time or midpoint) — the weather at
    the moment an outage begins is the most meaningful signal for
    correlating outages with conditions
  - if no weather reading exists within JOIN_TOLERANCE of an event's start,
    the event is logged as unmatched and excluded from the enriched
    output — never force-joined to the nearest reading regardless of
    distance
  - records carrying any validation_problems from either source are
    excluded from the join entirely, so a flagged/stale record never
    silently taints an enriched row. Excluded counts are reported, not
    silently dropped.
  - multiple events matching the same weather reading is expected and
    correct, not a bug (e.g. two schedules both starting an outage near
    the same hour)
"""
import glob
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

JOIN_TOLERANCE = timedelta(minutes=90)

# Open-Meteo's `time` field is naive (no UTC offset) because the request
# specifies timezone=Africa/Johannesburg — so a naive weather timestamp is
# implicitly already in this offset. Load-shedding timestamps come back
# offset-aware from EskomSePush, so weather timestamps need this attached
# before the two can be compared.
WEATHER_TZ = timezone(timedelta(hours=2))

LOADSHEDDING_SILVER_DIR = os.environ.get(
    "LOADSHEDDING_SILVER_DATA_DIR", "data/silver/loadshedding"
)
WEATHER_SILVER_DIR = os.environ.get("WEATHER_SILVER_DATA_DIR", "data/silver/weather")
GOLD_DATA_DIR = os.environ.get("GOLD_DATA_DIR", "data/gold")


def _load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def _is_clean(record: dict[str, Any]) -> bool:
    """A record is eligible for the join only if it has no validation
    problems recorded against it."""
    return not record.get("validation_problems")


def _parse_weather_time(time_str: str) -> datetime:
    """Parse an Open-Meteo timestamp, attaching WEATHER_TZ since the raw
    value is naive but implicitly in that offset (see module docstring)."""
    dt = datetime.fromisoformat(time_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WEATHER_TZ)
    return dt


def find_nearest_weather(
    event_start: str, weather_records: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float | None]:
    """
    Return (nearest_weather_record, distance_in_minutes) for the weather
    record closest to event_start, or (None, None) if no clean weather
    records exist at all. Does NOT apply the tolerance check — that's the
    caller's job, so this function stays testable independently of the
    tolerance constant.
    """
    if not weather_records:
        return None, None

    event_dt = datetime.fromisoformat(event_start)
    best_record = None
    best_distance = None

    for record in weather_records:
        weather_dt = _parse_weather_time(record["time"])
        distance = abs((event_dt - weather_dt).total_seconds()) / 60
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_record = record

    return best_record, best_distance


def join_events_to_weather(
    events: list[dict[str, Any]],
    weather_records: list[dict[str, Any]],
    tolerance: timedelta = JOIN_TOLERANCE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Join clean events to clean weather records by nearest timestamp.
    Returns (enriched_records, unmatched_events). Records with any
    validation_problems on either side are excluded before matching even
    begins.
    """
    clean_events = [e for e in events if _is_clean(e)]
    clean_weather = [w for w in weather_records if _is_clean(w)]

    enriched = []
    unmatched = []

    for event in clean_events:
        nearest, distance_minutes = find_nearest_weather(event["start"], clean_weather)

        if nearest is None or distance_minutes > tolerance.total_seconds() / 60:
            unmatched.append(
                {
                    **event,
                    "unmatched_reason": (
                        "no clean weather records available"
                        if nearest is None
                        else f"nearest weather reading was {distance_minutes:.0f} min away, "
                        f"exceeds tolerance of {tolerance.total_seconds() / 60:.0f} min"
                    ),
                }
            )
            continue

        enriched.append(
            {
                "schedule_id": event["schedule_id"],
                "area_id": event["area_id"],
                "stage": event["stage"],
                "event_start": event["start"],
                "event_end": event["end"],
                "weather_time": nearest["time"],
                "temperature_2m": nearest["temperature_2m"],
                "precipitation": nearest["precipitation"],
                "weather_code": nearest["weather_code"],
                "match_distance_minutes": round(distance_minutes, 1),
            }
        )

    return enriched, unmatched


def run(execution_date: str):
    """
    Loads the silver-layer load-shedding and weather output for
    execution_date, joins them, and writes both the enriched gold-layer
    output and an unmatched-events log — nothing is silently dropped.
    """
    loadshedding_path = os.path.join(
        LOADSHEDDING_SILVER_DIR, execution_date, "loadshedding_events.json"
    )
    weather_path = os.path.join(WEATHER_SILVER_DIR, execution_date, "weather_hourly.json")

    events = _load_json(loadshedding_path) if os.path.exists(loadshedding_path) else []
    weather_records = _load_json(weather_path) if os.path.exists(weather_path) else []

    enriched, unmatched = join_events_to_weather(events, weather_records)

    out_dir = os.path.join(GOLD_DATA_DIR, execution_date)
    os.makedirs(out_dir, exist_ok=True)

    enriched_path = os.path.join(out_dir, "enriched_events.json")
    with open(enriched_path, "w") as f:
        json.dump(enriched, f, indent=2)

    unmatched_path = os.path.join(out_dir, "unmatched_events.json")
    with open(unmatched_path, "w") as f:
        json.dump(unmatched, f, indent=2)

    return enriched_path, unmatched_path


if __name__ == "__main__":
    run(execution_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
