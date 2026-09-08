
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
    finally:
        conn.close()


if __name__ == "__main__":
    print_report()


def date_range_covered(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT MIN(execution_date), MAX(execution_date) FROM enriched_events;")
        return cur.fetchone()