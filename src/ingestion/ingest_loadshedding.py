"""
Pull raw load-shedding data from the EskomSePush API and land it untouched.

Design note: this module does NOT parse or validate the response. It only
fetches and writes raw JSON with a timestamp, so the raw layer is a faithful
record of what the API actually returned on a given run. Parsing happens in
src/transform/validate_transform_loadshedding.py.
"""
import json
import os
from datetime import datetime, timezone_

import requests

RAW_DATA_DIR = os.environ.get("RAW_DATA_DIR", "/opt/airflow/data/raw/loadshedding")

# EskomSePush requires a free API token — https://eskomsepush.gumroad.com/l/api
API_TOKEN = os.environ.get("ESP_API_TOKEN", "")
AREA_IDS = os.environ.get("ESP_AREA_IDS", "").split(",") if os.environ.get("ESP_AREA_IDS") else []

BASE_URL = "https://developer.sepush.co.za/business/2.0"


def fetch_status():
    """National load-shedding status (current stage)."""
    resp = requests.get(
        f"{BASE_URL}/status",
        headers={"Token": API_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_area_schedule(area_id: str):
    """Schedule for a specific area."""
    resp = requests.get(
        f"{BASE_URL}/area",
        headers={"Token": API_TOKEN},
        params={"id": area_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _land(payload: dict, filename: str, execution_date: str):
    out_dir = os.path.join(RAW_DATA_DIR, execution_date)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)
    with open(out_path, "w") as f:
        json.dump(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            },
            f,
            indent=2,
        )
    return out_path


def run(execution_date: str):
    status = fetch_status()
    _land(status, "status.json", execution_date)

    for area_id in AREA_IDS:
        area_id = area_id.strip()
        if not area_id:
            continue
        schedule = fetch_area_schedule(area_id)
        _land(schedule, f"area_{area_id}.json", execution_date)


if __name__ == "__main__":
    run(execution_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
