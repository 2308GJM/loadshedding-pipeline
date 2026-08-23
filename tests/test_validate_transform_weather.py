from src.transform.validate_transform_weather import (
    deduplicate_by_time,
    flatten_hourly_weather,
    validate_record,
)


def _record(**overrides):
    base = {"temperature_2m": 22.5, "time": "2026-08-17T18:00", "fetched_at": "2026-08-23T17:00:00+00:00"}
    base.update(overrides)
    return base


def test_flatten_zips_parallel_arrays_into_records():
    payload = {
        "hourly": {
            "time": ["2026-08-23T00:00", "2026-08-23T01:00"],
            "temperature_2m": [16.3, 15.8],
            "precipitation": [0.0, 0.1],
            "weather_code": [3, 2],
        }
    }
    records = flatten_hourly_weather(payload)
    assert len(records) == 2
    assert records[0]["time"] == "2026-08-23T00:00"
    assert records[0]["temperature_2m"] == 16.3
    assert records[1]["weather_code"] == 2


def test_valid_record_has_no_problems():
    assert validate_record(_record()) == []


def test_extreme_temperature_is_flagged():
    problems = validate_record(_record(temperature_2m=80))
    assert any("temperature" in p for p in problems)


def test_missing_temperature_is_flagged():
    problems = validate_record(_record(temperature_2m=None))
    assert any("temperature" in p for p in problems)


def test_missing_time_is_flagged():
    problems = validate_record(_record(time=""))
    assert any("time" in p for p in problems)


def test_deduplicate_by_time_keeps_most_recent_fetch():
    older = _record(time="2026-08-23T00:00", fetched_at="2026-08-23T10:00:00+00:00")
    newer = _record(time="2026-08-23T00:00", fetched_at="2026-08-23T12:00:00+00:00")
    result = deduplicate_by_time([older, newer])
    assert len(result) == 1
    assert result[0]["fetched_at"] == "2026-08-23T12:00:00+00:00"