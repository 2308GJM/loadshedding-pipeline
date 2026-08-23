"""
Pull raw weather data from the Open-Meteo API and land it untouched.

Open-Meteo requires no API key, which keeps this pipeline runnable by
anyone cloning the repo without a secrets setup for this source.
"""
import json
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

RAW_DATA_DIR = os.environ.get("WEATHER_RAW_DATA_DIR", "/opt/airflow/data/raw/weather")

# Default: Johannesburg. Override via env for other areas matched to
# load-shedding area IDs.
LATITUDE = os.environ.get("WEATHER_LAT", "-26.2041")
LONGITUDE = os.environ.get("WEATHER_LON", "28.0473")

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_hourly_weather():
    resp = requests.get(
        BASE_URL,
        params={
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "temperature_2m,precipitation,weather_code",
            "past_days": 1,
            "forecast_days": 1,
            "timezone": "Africa/Johannesburg",
        },
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
    weather = fetch_hourly_weather()
    _land(weather, "hourly.json", execution_date)


if __name__ == "__main__":
    run(execution_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
