"""`repo-pulse prs`: recent pull requests with author, age and review status."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import Annotated

import typer
from rich.table import Table

from repo_pulse import gh
from repo_pulse.metrics import Clock
from repo_pulse.models import PullRequest
from repo_pulse.render import age_cell, age_fields, render_report
from repo_pulse.reports._common import JsonOpt, RepoArg, fetch_or_exit, repo_title


class PrState(str, Enum):
    open = "open"
    closed = "closed"
    merged = "merged"
    all = "all"


StateOpt = Annotated[PrState, typer.Option(help="Filter by PR state.")]
LimitOpt = Annotated[int, typer.Option(min=1, help="Maximum number of PRs to list.")]

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
            **age_fields(pr.created_at, now),
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
            age_cell(pr.created_at, now),
            review_label(pr.review_decision),
        )
    return table


def register(app: typer.Typer, *, runner: gh.Runner | None, clock: Clock) -> None:
    @app.command()
    def prs(
        repo: RepoArg = None,
        state: StateOpt = PrState.open,
        limit: LimitOpt = 20,
        as_json: JsonOpt = False,
    ) -> None:
        """List recent pull requests with author, age and review status."""
        pull_requests = fetch_or_exit(gh.list_prs, repo, state=state.value, limit=limit, runner=runner)
        render_report(
            pull_requests,
            clock(),
            as_json=as_json,
            title=repo_title(repo, f"{state.value} pull requests"),
            noun="pull requests",
            to_dicts=prs_as_dicts,
            to_table=prs_table,
        )
