from src.transform.validate_transform_weather import validate_record


def _record(**overrides):
    base = {"temperature_2m": 22.5, "time": "2026-08-17T18:00"}
    base.update(overrides)
    return base


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
