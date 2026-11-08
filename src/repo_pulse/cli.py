"""Typer entry point. Kept thin: parse args, call gh.py, hand off to render.py.

`create_app` takes the gh runner and the clock as parameters so tests can
inject fakes; the module-level `app` uses the real ones.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

import typer

from repo_pulse import gh
from repo_pulse.metrics import Clock, utc_now
from repo_pulse.render import render_prs


class PrState(str, Enum):
    open = "open"
    closed = "closed"
    merged = "merged"
    all = "all"


def create_app(runner: gh.Runner | None = None, clock: Clock = utc_now) -> typer.Typer:
    app = typer.Typer(
        help="Quick health reports for GitHub repositories, powered by the gh CLI.",
        no_args_is_help=True,
        add_completion=False,
    )

    @app.callback()
    def main() -> None:
        """Quick health reports for GitHub repositories, powered by the gh CLI."""

    @app.command()
    def prs(
        repo: Annotated[
            Optional[str],
            typer.Argument(
                metavar="[OWNER/REPO]",
                help="Repository to inspect. Defaults to the current directory's repo.",
                show_default=False,
            ),
        ] = None,
        state: Annotated[PrState, typer.Option(help="Filter by PR state.")] = PrState.open,
        limit: Annotated[int, typer.Option(min=1, help="Maximum number of PRs to list.")] = 20,
        as_json: Annotated[bool, typer.Option("--json", help="Print JSON instead of a table.")] = False,
    ) -> None:
        """List recent pull requests with author, age and review status."""
        try:
            pull_requests = gh.list_prs(repo, state=state.value, limit=limit, runner=runner)
        except gh.GhError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1) from None

        title = f"{repo or 'current repo'}: {state.value} pull requests"
        render_prs(pull_requests, clock(), as_json=as_json, title=title)

    return app


app = create_app()
