"""
Tests for load_to_store.py.

These use a mocked psycopg2 connection rather than a live database, so the
test suite doesn't require Postgres to be running. The logic was verified
separately against a real Postgres instance — these tests lock that
verified behavior in for regression protection, they don't replace the
real-database check.
"""
import json
from unittest.mock import MagicMock, patch

from src.load.load_to_store import ensure_table, run, upsert_records


def _record(**overrides):
    base = {
        "schedule_id": "eskde-4",
        "area_id": "za_gt_jhb_sandown_so5u",
        "stage": 8,
        "event_start": "2026-08-23T15:28:58+02:00",
        "event_end": "2026-08-23T17:28:58+02:00",
        "weather_time": "2026-08-23T15:00",
        "temperature_2m": 25.0,
        "precipitation": 0.0,
        "weather_code": 0,
        "match_distance_minutes": 29.0,
    }
    base.update(overrides)
    return base


def _mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def test_ensure_table_executes_create_table_sql():
    conn, cursor = _mock_conn()
    ensure_table(conn)
    cursor.execute.assert_called_once()
    assert "CREATE TABLE IF NOT EXISTS enriched_events" in cursor.execute.call_args[0][0]
    conn.commit.assert_called_once()


def test_upsert_records_executes_once_per_record():
    conn, cursor = _mock_conn()
    records = [_record(schedule_id="eskde-3"), _record(schedule_id="eskde-4")]
    count = upsert_records(conn, records, execution_date="2026-08-23")
    assert count == 2
    assert cursor.execute.call_count == 2
    conn.commit.assert_called_once()


def test_upsert_records_passes_correct_params():
    conn, cursor = _mock_conn()
    upsert_records(conn, [_record()], execution_date="2026-08-23")
    _, params = cursor.execute.call_args[0]
    assert params["schedule_id"] == "eskde-4"
    assert params["execution_date"] == "2026-08-23"
    assert params["temperature_2m"] == 25.0


def test_run_returns_zero_when_no_gold_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("src.load.load_to_store.GOLD_DATA_DIR", str(tmp_path))
    assert run("2026-08-23") == 0


def test_run_returns_zero_for_empty_records_without_connecting(tmp_path, monkeypatch):
    monkeypatch.setattr("src.load.load_to_store.GOLD_DATA_DIR", str(tmp_path))
    day_dir = tmp_path / "2026-08-23"
    day_dir.mkdir()
    (day_dir / "enriched_events.json").write_text("[]")

    with patch("src.load.load_to_store.get_connection") as mock_get_conn:
        result = run("2026-08-23")
        assert result == 0
        mock_get_conn.assert_not_called()


def test_run_calls_ensure_table_and_upsert_with_real_records(tmp_path, monkeypatch):
    monkeypatch.setattr("src.load.load_to_store.GOLD_DATA_DIR", str(tmp_path))
    day_dir = tmp_path / "2026-08-23"
    day_dir.mkdir()
    (day_dir / "enriched_events.json").write_text(json.dumps([_record()]))

    conn, cursor = _mock_conn()
    with patch("src.load.load_to_store.get_connection", return_value=conn):
        result = run("2026-08-23")

    assert result == 1
    conn.close.assert_called_once()
