from datetime import datetime, timedelta, timezone

from src.transform.validate_transform_loadshedding import (
    deduplicate,
    validate_record,
)


def _record(**overrides):
    base = {
        "stage": 3,
        "area_id": "capetown-1",
        "start_time": "2026-08-17T18:00:00+02:00",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


def test_valid_record_has_no_problems():
    assert validate_record(_record()) == []


def test_stage_out_of_range_is_flagged():
    problems = validate_record(_record(stage=9))
    assert any("stage" in p for p in problems)


def test_missing_stage_is_flagged():
    problems = validate_record(_record(stage=None))
    assert any("stage" in p for p in problems)


def test_missing_area_id_is_flagged():
    problems = validate_record(_record(area_id=""))
    assert any("area_id" in p for p in problems)


def test_stale_record_is_flagged_not_dropped():
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    problems = validate_record(_record(fetched_at=stale_time))
    assert any("stale" in p for p in problems)


def test_deduplicate_keeps_most_recent_fetch():
    older = _record(fetched_at="2026-08-17T10:00:00+00:00")
    newer = _record(fetched_at="2026-08-17T12:00:00+00:00")
    result = deduplicate([older, newer])
    assert len(result) == 1
    assert result[0]["fetched_at"] == "2026-08-17T12:00:00+00:00"


def test_deduplicate_keeps_distinct_areas_separate():
    a = _record(area_id="capetown-1")
    b = _record(area_id="joburg-1")
    result = deduplicate([a, b])
    assert len(result) == 2
