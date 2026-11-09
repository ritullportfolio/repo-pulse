"""Turn models into terminal tables or JSON."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from rich.console import Console
from rich.table import Table

from repo_pulse.metrics import age, format_age
from repo_pulse.models import PullRequest, Release

REVIEW_LABELS = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "changes requested",
    "REVIEW_REQUIRED": "review required",
}


def review_label(decision: str | None) -> str:
    if decision is None:
        return "-"
    return REVIEW_LABELS.get(decision, decision.lower().replace("_", " "))


def prs_as_dicts(prs: Sequence[PullRequest], now: datetime) -> list[dict]:
    return [
        {
            "number": pr.number,
            "title": pr.title,
            "author": pr.author,
            "created_at": pr.created_at.isoformat(),
            "age_seconds": int(age(pr.created_at, now).total_seconds()),
            "age": format_age(age(pr.created_at, now)),
            "review_decision": pr.review_decision,
            "url": pr.url,
        }
        for pr in prs
    ]


def prs_table(prs: Sequence[PullRequest], now: datetime, title: str) -> Table:
    table = Table(title=title)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("Author", no_wrap=True)
    table.add_column("Age", justify="right", no_wrap=True)
    table.add_column("Review", no_wrap=True)
    for pr in prs:
        table.add_row(
            str(pr.number),
            pr.title,
            pr.author,
            format_age(age(pr.created_at, now)),
            review_label(pr.review_decision),
        )
    return table


def render_prs(
    prs: Sequence[PullRequest],
    now: datetime,
    *,
    as_json: bool,
    title: str,
    console: Console | None = None,
) -> None:
    console = console or Console()
    if as_json:
        # Plain print so rich doesn't add colour or wrapping to machine output.
        print(json.dumps(prs_as_dicts(prs, now), indent=2))
    elif not prs:
        console.print(f"No pull requests found ({title}).")
    else:
        console.print(prs_table(prs, now, title))


def release_status(release: Release) -> str:
    # A draft or pre-release is never "latest", so check those first.
    if release.is_draft:
        return "draft"
    if release.is_prerelease:
        return "pre-release"
    if release.is_latest:
        return "latest"
    return "-"


def releases_as_dicts(releases: Sequence[Release], now: datetime) -> list[dict]:
    return [
        {
            "tag": r.tag,
            "name": r.name,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "created_at": r.created_at.isoformat(),
            "age_seconds": int(age(r.released_at, now).total_seconds()),
            "age": format_age(age(r.released_at, now)),
            "is_latest": r.is_latest,
            "is_prerelease": r.is_prerelease,
            "is_draft": r.is_draft,
        }
        for r in releases
    ]


def releases_table(releases: Sequence[Release], now: datetime, title: str) -> Table:
    table = Table(title=title)
    table.add_column("Tag", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Age", justify="right", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    for r in releases:
        table.add_row(
            r.tag,
            r.name or "-",
            format_age(age(r.released_at, now)),
            release_status(r),
        )
    return table


def render_releases(
    releases: Sequence[Release],
    now: datetime,
    *,
    as_json: bool,
    title: str,
    console: Console | None = None,
) -> None:
    console = console or Console()
    if as_json:
        # Plain print so rich doesn't add colour or wrapping to machine output.
        print(json.dumps(releases_as_dicts(releases, now), indent=2))
    elif not releases:
        console.print(f"No releases found ({title}).")
    else:
        console.print(releases_table(releases, now, title))
