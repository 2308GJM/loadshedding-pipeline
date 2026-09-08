"""
Queries the enriched_events table and prints summary statistics:
event count by stage, temperature by stage, events by hour of day,
and join match quality.
"""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

PIPELINE_DB_HOST = os.environ.get("PIPELINE_DB_HOST", "pipeline-db")
PIPELINE_DB_PORT = os.environ.get("PIPELINE_DB_PORT", "5432")
PIPELINE_DB_NAME = os.environ.get("PIPELINE_DB_NAME", "loadshedding")
PIPELINE_DB_USER = os.environ.get("PIPELINE_DB_USER", "pipeline")
PIPELINE_DB_PASSWORD = os.environ.get("PIPELINE_DB_PASSWORD", "pipeline")


def get_connection():
    return psycopg2.connect(
        host=PIPELINE_DB_HOST,
        port=PIPELINE_DB_PORT,
        dbname=PIPELINE_DB_NAME,
        user=PIPELINE_DB_USER,
        password=PIPELINE_DB_PASSWORD,
    )


def total_row_count(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM enriched_events;")
        return cur.fetchone()[0]


def print_report():
    conn = get_connection()
    try:
        total = total_row_count(conn)
        print(f"=== Total enriched events: {total} ===\n")

        earliest, latest = date_range_covered(conn)
        print(f"Date range covered: {earliest} to {latest}\n")

        print("--- Stage distribution ---")
        for stage, count in stage_distribution(conn):
            print(f"  Stage {stage}: {count} events")

        print("\n--- Temperature by stage ---")
        for stage, count, avg_temp, min_temp, max_temp in temperature_by_stage(conn):
            print(f"  Stage {stage} ({count} events): avg {avg_temp}°C, range {min_temp}-{max_temp}°C")

        if total == 0:
            print("No data yet — run the pipeline first.")
            return

            print("\n--- Events by hour of day ---")
        for hour, count, avg_temp in events_by_hour_of_day(conn):
            print(f"  {int(hour):02d}:00 — {count} events, avg {avg_temp}°C")

        avg_dist, max_dist, min_dist = match_quality(conn)
        print(f"\n--- Join match quality ---")
        print(f"  Average distance to matched weather reading: {avg_dist} min")
        print(f"  Range: {min_dist}-{max_dist} min")

    finally:
        conn.close()

def date_range_covered(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT MIN(execution_date), MAX(execution_date) FROM enriched_events;")
        return cur.fetchone()

def stage_distribution(conn):
    """How many events at each stage — tells you whether there's enough
    variation in stage to say anything meaningful about it."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT stage, COUNT(*) as event_count
            FROM enriched_events
            GROUP BY stage
            ORDER BY stage;
            """
        )
        return cur.fetchall()

def temperature_by_stage(conn):
    """Average, min, max temperature observed at each stage — the core
    input to the "does stage correlate with temperature" question."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                stage,
                COUNT(*) as event_count,
                ROUND(AVG(temperature_2m), 1) as avg_temp,
                MIN(temperature_2m) as min_temp,
                MAX(temperature_2m) as max_temp
            FROM enriched_events
            GROUP BY stage
            ORDER BY stage;
            """
        )
        return cur.fetchall()

def events_by_hour_of_day(conn):
    """Does load-shedding cluster at particular hours? Extracts the hour
    from event_start and counts events per hour."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                EXTRACT(HOUR FROM event_start) as hour_of_day,
                COUNT(*) as event_count,
                ROUND(AVG(temperature_2m), 1) as avg_temp
            FROM enriched_events
            GROUP BY hour_of_day
            ORDER BY hour_of_day;
            """
        )
        return cur.fetchall()


def match_quality(conn):
    """How close were the join matches, on average? A high average
    match_distance_minutes would be worth flagging as a limitation."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ROUND(AVG(match_distance_minutes), 1) as avg_distance,
                MAX(match_distance_minutes) as max_distance,
                MIN(match_distance_minutes) as min_distance
            FROM enriched_events;
            """
        )
        return cur.fetchone()
if __name__ == "__main__":
    print_report()


