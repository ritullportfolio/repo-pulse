"""Pure functions over model data. No I/O and no reading of the system clock:
callers pass `now` in explicitly."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

Clock = Callable[[], datetime]


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
