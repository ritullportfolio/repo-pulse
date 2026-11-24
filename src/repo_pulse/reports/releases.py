"""`repo-pulse releases`: the latest releases with tag, name, age and status."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

import typer
from rich.table import Table

from repo_pulse import gh
from repo_pulse.metrics import Clock, is_at_or_after
from repo_pulse.models import Release
from repo_pulse.render import age_cell, age_fields, render_report
from repo_pulse.reports._common import (
    JsonOpt,
    RepoArg,
    SinceOpt,
    fetch_or_exit,
    repo_title,
    since_cutoff,
)

ReleaseLimitOpt = Annotated[int, typer.Option(min=1, help="Maximum number of releases to list.")]


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
            **age_fields(r.released_at, now),
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
            age_cell(r.released_at, now),
            release_status(r),
        )
    return table


def register(app: typer.Typer, *, runner: gh.Runner | None, clock: Clock) -> None:
    @app.command()
    def releases(
        repo: RepoArg = None,
        limit: ReleaseLimitOpt = 10,
        since: SinceOpt = None,
        as_json: JsonOpt = False,
    ) -> None:
        """List the latest releases with tag, name, age and status."""
        now = clock()
        cutoff = since_cutoff(since, now)  # a bad value exits 2 before gh runs
        release_list = fetch_or_exit(gh.list_releases, repo, limit=limit, runner=runner)
        # gh release list can't filter by date. Check every item rather than stopping
        # at the first old one: gh sorts by creation date, but released_at prefers
        # publishedAt, so the list isn't strictly ordered by it.
        release_list = [r for r in release_list if is_at_or_after(r.released_at, cutoff)]
        render_report(
            release_list,
            now,
            as_json=as_json,
            title=repo_title(repo, "latest releases", since),
            noun="releases",
            to_dicts=releases_as_dicts,
            to_table=releases_table,
        )
