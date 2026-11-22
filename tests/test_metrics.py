from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from repo_pulse.metrics import age, format_age
from repo_pulse.metrics import is_since, parse_since
from tests.conftest import NOW


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=0), "just now"),
        (timedelta(seconds=59), "just now"),
        (timedelta(minutes=1), "1m"),
        (timedelta(minutes=59), "59m"),
        (timedelta(hours=1), "1h"),
        (timedelta(hours=23, minutes=59), "23h"),
        (timedelta(days=1), "1d"),
        (timedelta(days=13), "13d"),
        (timedelta(days=14), "2w"),
        (timedelta(days=364), "52w"),
        (timedelta(days=365), "1y"),
        (timedelta(days=800), "2y"),
    ],
)
def test_format_age(delta: timedelta, expected: str) -> None:
    assert format_age(delta) == expected


def test_age_uses_injected_now() -> None:
    assert age(NOW - timedelta(days=2), NOW) == timedelta(days=2)


def test_age_is_never_negative() -> None:
    assert age(NOW + timedelta(minutes=5), NOW) == timedelta(0)


# --- parse_since / is_since ------------------------------------------------------

UTC = timezone.utc


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30m", datetime(2026, 1, 15, 11, 30, tzinfo=UTC)),
        ("12h", datetime(2026, 1, 15, 0, 0, tzinfo=UTC)),
        ("7d", datetime(2026, 1, 8, 12, 0, tzinfo=UTC)),
        ("2w", datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
        ("1y", datetime(2025, 1, 15, 12, 0, tzinfo=UTC)),
        (" 7d ", datetime(2026, 1, 8, 12, 0, tzinfo=UTC)),
    ],
)
def test_parse_since_durations_count_back_from_now(value: str, expected: datetime) -> None:
    assert parse_since(value, NOW) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # A plain date is midnight UTC.
        ("2026-10-01", datetime(2026, 10, 1, 0, 0, tzinfo=UTC)),
        # A datetime without a timezone is UTC too.
        ("2026-10-01T08:30", datetime(2026, 10, 1, 8, 30, tzinfo=UTC)),
        ("2026-10-01T08:30Z", datetime(2026, 10, 1, 8, 30, tzinfo=UTC)),
        # An offset is converted to UTC: local midnight in India is 18:30 UTC the day before.
        ("2026-10-01T00:00+05:30", datetime(2026, 9, 30, 18, 30, tzinfo=UTC)),
    ],
)
def test_parse_since_dates_and_datetimes(value: str, expected: datetime) -> None:
    result = parse_since(value, NOW)
    assert result == expected
    assert result.utcoffset() == timedelta(0)


@pytest.mark.parametrize("value", ["", "7", "7x", "-3d", "d", "1.5d", "yesterday", "2026-13-01"])
def test_parse_since_rejects_bad_values(value: str) -> None:
    with pytest.raises(ValueError, match="expected a duration like 7d"):
        parse_since(value, NOW)


def test_parse_since_rejects_zero_duration() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        parse_since("0d", NOW)


def test_is_since() -> None:
    cutoff = NOW - timedelta(days=1)
    assert is_since(NOW, cutoff)
    assert is_since(cutoff, cutoff)  # exactly at the cutoff counts as newer
    assert not is_since(cutoff - timedelta(seconds=1), cutoff)
    assert is_since(datetime(2000, 1, 1, tzinfo=UTC), None)
