from __future__ import annotations

from datetime import timedelta

import pytest

from repo_pulse.metrics import age, format_age
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
