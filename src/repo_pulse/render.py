"""Shared output for every report: age formatting and the JSON / empty / table switch.

Report-specific rows and tables live in each `repo_pulse.reports` module.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, TypeVar

from rich.console import Console
from rich.table import Table

from repo_pulse.metrics import age, format_age

T = TypeVar("T")


def age_fields(when: datetime, now: datetime) -> dict[str, Any]:
    """The two age keys every report's JSON rows share."""
    delta = age(when, now)
    return {"age_seconds": int(delta.total_seconds()), "age": format_age(delta)}


def age_cell(when: datetime, now: datetime) -> str:
    """Compact age for a table cell, e.g. '3d'."""
    return format_age(age(when, now))


def render_report(
    items: Sequence[T],
    now: datetime,
    *,
    as_json: bool,
    title: str,
    noun: str,
    to_dicts: Callable[[Sequence[T], datetime], list[dict]],
    to_table: Callable[[Sequence[T], datetime, str], Table],
    console: Console | None = None,
) -> None:
    """Print a report as JSON, a 'nothing found' line, or a rich table."""
    console = console or Console()
    if as_json:
        # Plain print so rich doesn't add colour or wrapping to machine output.
        print(json.dumps(to_dicts(items, now), indent=2))
    elif not items:
        console.print(f"No {noun} found ({title}).")
    else:
        console.print(to_table(items, now, title))
