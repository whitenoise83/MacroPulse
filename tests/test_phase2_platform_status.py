from __future__ import annotations

from datetime import date

from macropulse.platform.status import (
    classify_source_freshness,
    freshness_threshold_days,
)


def test_frequency_thresholds_are_platform_operational() -> None:
    assert freshness_threshold_days("D") == 10
    assert freshness_threshold_days("W") == 21
    assert freshness_threshold_days("M") == 75
    assert freshness_threshold_days("Q") == 180
    assert freshness_threshold_days("unknown") == 90


def test_fresh_source_without_due_release() -> None:
    result = classify_source_freshness(
        latest_observation_date=date(2026, 7, 31),
        frequency="M",
        as_of=date(2026, 8, 7),
        release_due=False,
    )
    assert result["freshness_state"] == "fresh"
    assert result["stale"] is False


def test_release_after_run_makes_source_stale() -> None:
    result = classify_source_freshness(
        latest_observation_date=date(2026, 7, 31),
        frequency="M",
        as_of=date(2026, 8, 7),
        release_due=True,
    )
    assert result["freshness_state"] == "stale_release_due"
    assert result["stale"] is True


def test_old_source_is_stale_by_age() -> None:
    result = classify_source_freshness(
        latest_observation_date=date(2026, 4, 1),
        frequency="M",
        as_of=date(2026, 8, 7),
        release_due=False,
    )
    assert result["freshness_state"] == "stale_age"
    assert result["stale"] is True


def test_unknown_frequency_fails_closed() -> None:
    result = classify_source_freshness(
        latest_observation_date=date(2026, 8, 1),
        frequency=None,
        as_of=date(2026, 8, 7),
        release_due=False,
    )
    assert result["freshness_state"] == "indeterminate_frequency"
    assert result["stale"] is True

def test_fred_descriptive_frequency_labels_are_normalised() -> None:
    weekly = classify_source_freshness(
        latest_observation_date=date(2026, 7, 18),
        frequency="Weekly, Ending Saturday",
        as_of=date(2026, 8, 7),
        release_due=False,
    )
    assert weekly["frequency"] == "W"
    assert weekly["threshold_days"] == 21
    assert weekly["freshness_state"] == "fresh"
    assert weekly["stale"] is False

