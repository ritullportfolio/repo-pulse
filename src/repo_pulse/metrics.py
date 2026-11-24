"""Pure functions over model data. No I/O and no reading of the system clock:
callers pass `now` in explicitly."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

Clock = Callable[[], datetime]

# The same units format_age prints. A "year" is 365 days.
_SINCE_UNITS = {
    "m": timedelta(minutes=1),
    "h": timedelta(hours=1),
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
    "y": timedelta(days=365),
}
_DURATION_RE = re.compile(r"(\d+)([mhdwy])")
_SINCE_HELP = "expected a duration like 7d, 12h, 2w or an ISO date like 2026-10-01"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def age(created_at: datetime, now: datetime) -> timedelta:
    """Time elapsed since created_at. Never negative (guards against clock skew)."""
    return max(now - created_at, timedelta(0))


def format_age(delta: timedelta) -> str:
    """Compact human age: 'just now', '45m', '5h', '3d', '6w', '2y'."""
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 14:
        return f"{days}d"
    if days < 365:
        return f"{days // 7}w"
    return f"{days // 365}y"


def parse_since(value: str, now: datetime) -> datetime:
    """Turn a --since value into a UTC cutoff.

    Accepts a duration back from `now` ('30m', '12h', '7d', '2w', '1y'), an ISO
    date ('2026-10-01', meaning midnight UTC) or an ISO datetime (no timezone
    means UTC). Raises ValueError with a user-facing message otherwise.
    """
    try:
        return _parse_since(value.strip(), now)
    except OverflowError:
        # e.g. 3000y, or an offset that pushes a datetime past year 1 or 9999.
        raise ValueError(f"{value!r}: too far in the past or future") from None


def _parse_since(text: str, now: datetime) -> datetime:
    match = _DURATION_RE.fullmatch(text)
    if match:
        count = int(match.group(1))
        if count == 0:
            raise ValueError(f"{text!r}: duration must be greater than zero")
        return now - count * _SINCE_UNITS[match.group(2)]

    try:
        if len(text) == 10:  # a plain date: YYYY-MM-DD
            day = date.fromisoformat(text)
            return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{text!r}: {_SINCE_HELP}") from None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_at_or_after(when: datetime, cutoff: datetime | None) -> bool:
    """True if `when` is at or after `cutoff`; always True with no cutoff."""
    return cutoff is None or when >= cutoff
