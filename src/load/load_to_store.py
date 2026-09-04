"""
Load the enriched gold-layer dataset into the serving store (PostgreSQL).

Design contract (see docs/decisions.md):
  - writes are idempotent per (schedule_id, event_start) — re-running this
    task for a given execution_date upserts rather than duplicates, so DAG
    retries never corrupt the data
  - weather_time is stored as a plain (non-timezone-aware) TIMESTAMP,
    deliberately NOT TIMESTAMPTZ — Open-Meteo's time field is naive but
    implicitly in +02:00 (see join_enrich.py's WEATHER_TZ comment); storing
    it as TIMESTAMPTZ would make Postgres wrongly assume UTC
  - the table is created if it doesn't exist, so this module can run
    against a fresh database with no separate migration step
"""
import json
import os
from datetime import datetime, timezone
from typing import Any

import psycopg2
from dotenv import load_dotenv

load_dotenv()

GOLD_DATA_DIR = os.environ.get("GOLD_DATA_DIR", "data/gold")

# Defaults match docker-compose.yml's pipeline-db service. PIPELINE_DB_HOST
# defaults to "pipeline-db" (the container hostname, resolvable inside the
# Docker network) but should be overridden to "localhost" for local dev
# outside Docker, where PIPELINE_DB_PORT should be 5433 (the host-mapped
# port), not Postgres's default 5432.
PIPELINE_DB_HOST = os.environ.get("PIPELINE_DB_HOST", "pipeline-db")
PIPELINE_DB_PORT = os.environ.get("PIPELINE_DB_PORT", "5432")
PIPELINE_DB_NAME = os.environ.get("PIPELINE_DB_NAME", "loadshedding")
PIPELINE_DB_USER = os.environ.get("PIPELINE_DB_USER", "pipeline")
PIPELINE_DB_PASSWORD = os.environ.get("PIPELINE_DB_PASSWORD", "pipeline")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS enriched_events (
    id                      SERIAL PRIMARY KEY,
    execution_date          DATE NOT NULL,
    schedule_id             TEXT NOT NULL,
    area_id                 TEXT,
    stage                   INTEGER NOT NULL,
    event_start             TIMESTAMPTZ NOT NULL,
    event_end               TIMESTAMPTZ NOT NULL,
    weather_time            TIMESTAMP NOT NULL,
    temperature_2m          NUMERIC(4,1),
    precipitation           NUMERIC(5,2),
    weather_code            INTEGER,
    match_distance_minutes  NUMERIC(5,1),
    loaded_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (schedule_id, event_start)
);
"""

UPSERT_SQL = """
INSERT INTO enriched_events (
    execution_date, schedule_id, area_id, stage,
    event_start, event_end, weather_time,
    temperature_2m, precipitation, weather_code, match_distance_minutes
) VALUES (
    %(execution_date)s, %(schedule_id)s, %(area_id)s, %(stage)s,
    %(event_start)s, %(event_end)s, %(weather_time)s,
    %(temperature_2m)s, %(precipitation)s, %(weather_code)s, %(match_distance_minutes)s
)
ON CONFLICT (schedule_id, event_start) DO UPDATE SET
    execution_date = EXCLUDED.execution_date,
    area_id = EXCLUDED.area_id,
    stage = EXCLUDED.stage,
    event_end = EXCLUDED.event_end,
    weather_time = EXCLUDED.weather_time,
    temperature_2m = EXCLUDED.temperature_2m,
    precipitation = EXCLUDED.precipitation,
    weather_code = EXCLUDED.weather_code,
    match_distance_minutes = EXCLUDED.match_distance_minutes,
    loaded_at = now();
"""


def get_connection():
    return psycopg2.connect(
        host=PIPELINE_DB_HOST,
        port=PIPELINE_DB_PORT,
        dbname=PIPELINE_DB_NAME,
        user=PIPELINE_DB_USER,
        password=PIPELINE_DB_PASSWORD,
    )


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()


def upsert_records(conn, records: list[dict[str, Any]], execution_date: str) -> int:
    """Upsert enriched records, returns the count written."""
    with conn.cursor() as cur:
        for record in records:
            cur.execute(
                UPSERT_SQL,
                {
                    "execution_date": execution_date,
                    "schedule_id": record["schedule_id"],
                    "area_id": record.get("area_id"),
                    "stage": record["stage"],
                    "event_start": record["event_start"],
                    "event_end": record["event_end"],
                    "weather_time": record["weather_time"],
                    "temperature_2m": record.get("temperature_2m"),
                    "precipitation": record.get("precipitation"),
                    "weather_code": record.get("weather_code"),
                    "match_distance_minutes": record.get("match_distance_minutes"),
                },
            )
    conn.commit()
    return len(records)


def run(execution_date: str) -> int:
    """
    Loads enriched_events.json from the gold layer for execution_date and
    upserts every record into the pipeline-db enriched_events table.
    Returns the number of records written.
    """
    enriched_path = os.path.join(GOLD_DATA_DIR, execution_date, "enriched_events.json")
    if not os.path.exists(enriched_path):
        return 0

    with open(enriched_path) as f:
        records = json.load(f)

    if not records:
        return 0

    conn = get_connection()
    try:
        ensure_table(conn)
        count = upsert_records(conn, records, execution_date)
    finally:
        conn.close()

    return count


if __name__ == "__main__":
    written = run(execution_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    print(f"Wrote {written} records")
