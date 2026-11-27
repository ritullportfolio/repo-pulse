"""`repo-pulse summary`: one health overview built from the prs and releases data."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from repo_pulse import gh
from repo_pulse.metrics import Clock, is_at_or_after, summarize
from repo_pulse.models import PullRequest, Release, RepoSummary
from repo_pulse.render import age_cell, age_fields
from repo_pulse.reports._common import (
    JsonOpt,
    RepoArg,
    SinceOpt,
    fetch_or_exit,
    repo_title,
    resolve_repo,
    since_cutoff,
)
from repo_pulse.reports.releases import release_status

SummaryLimitOpt = Annotated[
    int,
    typer.Option(
        min=1,
        help="Maximum number of open PRs to fetch. Counts stop here and show as N+.",
    ),
]

# The latest release is almost always among the newest few; 20 leaves room for
# a run of pre-releases or drafts on top of it.
RELEASE_LIMIT = 20


def _pr_dict(pr: PullRequest | None, now: datetime) -> dict[str, Any] | None:
    if pr is None:
        return None
    return {
        "number": pr.number,
        "title": pr.title,
        "author": pr.author,
        "created_at": pr.created_at.isoformat(),
        **age_fields(pr.created_at, now),
        "url": pr.url,
    }


def _release_dict(release: Release | None, now: datetime) -> dict[str, Any] | None:
    if release is None:
        return None
    return {
        "tag": release.tag,
        "name": release.name,
        "status": release_status(release),
        "published_at": release.published_at.isoformat() if release.published_at else None,
        "created_at": release.created_at.isoformat(),
        **age_fields(release.released_at, now),
    }


def summary_as_dict(summary: RepoSummary, now: datetime, *, limit_reached: bool) -> dict:
    return {
        "open_prs": summary.open_prs,
        "open_prs_limit_reached": limit_reached,
        "prs_needing_review": summary.prs_needing_review,
        "oldest_open_pr": _pr_dict(summary.oldest_open_pr, now),
        "latest_release": _release_dict(summary.latest_release, now),
        "newer_unreleased": _release_dict(summary.newer_unreleased, now),
    }


def summary_table(summary: RepoSummary, now: datetime, title: str, *, limit_reached: bool) -> Table:
    table = Table(title=title, show_header=False)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value")

    plus = "+" if limit_reached else ""
    table.add_row("Open PRs", f"{summary.open_prs}{plus}")
    table.add_row("Needing review", f"{summary.prs_needing_review}{plus}")

    pr = summary.oldest_open_pr
    table.add_row(
        "Oldest open PR",
        f"#{pr.number} {pr.title} ({age_cell(pr.created_at, now)})" if pr else "-",
    )

    latest = summary.latest_release
    table.add_row(
        "Latest release",
        f"{latest.tag} ({age_cell(latest.released_at, now)})" if latest else "-",
    )

    newer = summary.newer_unreleased
    table.add_row(
        "Newer pre-release/draft",
        f"{newer.tag} {release_status(newer)} ({age_cell(newer.released_at, now)})"
        if newer
        else "-",
    )
    return table


def register(app: typer.Typer, *, runner: gh.Runner | None, clock: Clock) -> None:
    @app.command()
    def summary(
        ctx: typer.Context,
        repo: RepoArg = None,
        limit: SummaryLimitOpt = 100,
        since: SinceOpt = None,
        as_json: JsonOpt = False,
    ) -> None:
        """Health overview: open PRs, review backlog and the latest release."""
        repo = resolve_repo(ctx, repo)
        now = clock()
        cutoff = since_cutoff(since, now)  # a bad value exits 2 before gh runs
        # Any gh failure exits 1 with the usual error, rather than a partial summary.
        open_prs = fetch_or_exit(
            gh.list_prs, repo, state="open", limit=limit, cutoff=cutoff, runner=runner
        )
        limit_reached = len(open_prs) >= limit
        releases = fetch_or_exit(gh.list_releases, repo, limit=RELEASE_LIMIT, runner=runner)

        # Same trimming as the prs and releases reports.
        open_prs = [pr for pr in open_prs if is_at_or_after(pr.created_at, cutoff)]
        releases = [r for r in releases if is_at_or_after(r.released_at, cutoff)]
        result = summarize(open_prs, releases)

        if as_json:
            # Plain print, one object (not a list), so it stays machine-readable.
            print(json.dumps(summary_as_dict(result, now, limit_reached=limit_reached), indent=2))
        else:
            title = repo_title(repo, "summary", since)
            Console().print(summary_table(result, now, title, limit_reached=limit_reached))
