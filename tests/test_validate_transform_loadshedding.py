from datetime import datetime, timedelta, timezone

from src.transform.validate_transform_loadshedding import (
    deduplicate,
    validate_record,
    flatten_schedule_events,
    parse_stage_from_note,
)


def _record(**overrides):
    base = {
        "schedule_id": "eskde-4",
        "area_id": "za_gt_jhb_sandown_so5u",
        "stage": 8,
        "note": "Stage 8 (TESTING: current)",
        "start": "2026-08-23T15:28:58+02:00",
        "end": "2026-08-23T17:28:58+02:00",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


def test_parses_stage_number_from_note():
    assert parse_stage_from_note("Stage 8 (TESTING: current)") == 8


def test_parses_stage_number_without_suffix():
    assert parse_stage_from_note("Stage 2") == 2


def test_returns_none_for_note_without_stage():
    assert parse_stage_from_note("Load Reduction") is None


def test_returns_none_for_empty_note():
    assert parse_stage_from_note("") is None


def test_flattens_events_into_flat_records():
    payload = {
        "events": [
            {"start": "2026-08-23T15:00:00+02:00", "end": "2026-08-23T17:00:00+02:00", "note": "Stage 4"}
        ],
        "schedule": {"days": []},
    }
    records = flatten_schedule_events(payload, schedule_id="eskde-4", area_id="area-1")
    assert len(records) == 1
    assert records[0]["schedule_id"] == "eskde-4"
    assert records[0]["area_id"] == "area-1"
    assert records[0]["stage"] == 4
    assert records[0]["start"] == "2026-08-23T15:00:00+02:00"


def test_flatten_ignores_schedule_days_entirely():
    payload = {"events": [], "schedule": {"days": [{"date": "2026-08-23"}]}}
    records = flatten_schedule_events(payload, schedule_id="eskde-4")
    assert records == []


def test_valid_record_has_no_problems():
    assert validate_record(_record()) == []


def test_stage_out_of_range_is_flagged():
    problems = validate_record(_record(stage=9))
    assert any("stage" in p for p in problems)


def test_unparseable_stage_is_flagged():
    problems = validate_record(_record(stage=None, note="Load Reduction"))
    assert any("stage" in p for p in problems)


def test_end_before_start_is_flagged():
    problems = validate_record(_record(
        start="2026-08-23T17:00:00+02:00",
        end="2026-08-23T15:00:00+02:00",
    ))
    assert any("not after start" in p for p in problems)


def test_missing_start_is_flagged():
    problems = validate_record(_record(start=None))
    assert any("start" in p for p in problems)


def test_stale_record_is_flagged_not_dropped():
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    problems = validate_record(_record(fetched_at=stale_time))
    assert any("stale" in p for p in problems)


def test_deduplicate_keeps_most_recent_fetch():
    older = _record(fetched_at="2026-08-23T10:00:00+00:00")
    newer = _record(fetched_at="2026-08-23T12:00:00+00:00")
    result = deduplicate([older, newer])
    assert len(result) == 1
    assert result[0]["fetched_at"] == "2026-08-23T12:00:00+00:00"


def test_deduplicate_keeps_distinct_events_separate():
    a = _record(start="2026-08-23T15:00:00+02:00", end="2026-08-23T17:00:00+02:00")
    b = _record(start="2026-08-23T20:00:00+02:00", end="2026-08-23T22:00:00+02:00")
    result = deduplicate([a, b])
    assert len(result) == 2