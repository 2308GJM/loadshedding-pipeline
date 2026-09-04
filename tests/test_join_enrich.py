from src.transform.join_enrich import (
    JOIN_TOLERANCE,
    find_nearest_weather,
    join_events_to_weather,
)


def _event(**overrides):
    base = {
        "schedule_id": "eskde-4",
        "area_id": "za_gt_jhb_sandown_so5u",
        "stage": 8,
        "start": "2026-08-23T15:28:58+02:00",
        "end": "2026-08-23T17:28:58+02:00",
        "validation_problems": [],
    }
    base.update(overrides)
    return base


def _weather(**overrides):
    base = {
        "time": "2026-08-23T15:00",
        "temperature_2m": 24.5,
        "precipitation": 0.0,
        "weather_code": 1,
        "validation_problems": [],
    }
    base.update(overrides)
    return base


def test_finds_closest_record_by_start_time():
    weather = [_weather(time="2026-08-23T13:00"), _weather(time="2026-08-23T15:00")]
    nearest, distance = find_nearest_weather("2026-08-23T15:28:58+02:00", weather)
    assert nearest["time"] == "2026-08-23T15:00"
    assert round(distance) == 29


def test_returns_none_when_no_weather_records():
    nearest, distance = find_nearest_weather("2026-08-23T15:28:58+02:00", [])
    assert nearest is None
    assert distance is None


def test_naive_weather_timestamps_compare_correctly_against_aware_event_times():
    weather = [_weather(time="2026-08-23T15:00")]
    nearest, distance = find_nearest_weather("2026-08-23T15:28:58+02:00", weather)
    assert nearest is not None
    assert distance is not None


def test_clean_event_matches_within_tolerance():
    enriched, unmatched = join_events_to_weather([_event()], [_weather()])
    assert len(enriched) == 1
    assert len(unmatched) == 0
    assert enriched[0]["temperature_2m"] == 24.5


def test_two_events_can_match_the_same_weather_reading():
    events = [
        _event(schedule_id="eskde-4", start="2026-08-23T15:28:58+02:00"),
        _event(schedule_id="eskde-3", start="2026-08-23T15:28:59+02:00"),
    ]
    enriched, unmatched = join_events_to_weather(events, [_weather()])
    assert len(enriched) == 2
    assert enriched[0]["weather_time"] == enriched[1]["weather_time"]


def test_flagged_event_is_excluded_from_join_entirely():
    flagged = _event(validation_problems=["stage out of range"])
    enriched, unmatched = join_events_to_weather([flagged], [_weather()])
    assert len(enriched) == 0
    assert len(unmatched) == 0


def test_flagged_weather_record_is_excluded_from_candidate_pool():
    flagged_weather = _weather(validation_problems=["stale record"])
    enriched, unmatched = join_events_to_weather([_event()], [flagged_weather])
    assert len(enriched) == 0
    assert len(unmatched) == 1


def test_event_outside_tolerance_is_logged_unmatched_not_dropped():
    far_event = _event(start="2026-08-25T03:00:00+02:00")
    enriched, unmatched = join_events_to_weather([far_event], [_weather()])
    assert len(enriched) == 0
    assert len(unmatched) == 1
    assert "exceeds tolerance" in unmatched[0]["unmatched_reason"]


def test_no_weather_at_all_is_logged_unmatched_with_clear_reason():
    enriched, unmatched = join_events_to_weather([_event()], [])
    assert len(enriched) == 0
    assert len(unmatched) == 1
    assert "no clean weather records" in unmatched[0]["unmatched_reason"]


def test_custom_tolerance_is_respected():
    from datetime import timedelta
    event = _event(start="2026-08-23T16:30:00+02:00")
    enriched, unmatched = join_events_to_weather(
        [event], [_weather()], tolerance=timedelta(minutes=30)
    )
    assert len(enriched) == 0
    assert len(unmatched) == 1
