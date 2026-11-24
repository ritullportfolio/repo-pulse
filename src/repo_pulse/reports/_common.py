"""Pieces every report command shares: the repo argument, --json, and gh error handling.

Import these at module level in a report module. With `from __future__ import
annotations`, Typer resolves a command's annotations against its module's
globals, so annotation types defined inside `register()` would not be found.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional, TypeVar

import typer

from repo_pulse import gh
from repo_pulse.config import Config, ConfigError, load_config
from repo_pulse.metrics import parse_since

T = TypeVar("T")

RepoArg = Annotated[
    Optional[str],
    typer.Argument(
        metavar="[OWNER/REPO]",
        help=(
            "Repository to inspect. Defaults to default_repo from the config file, "
            "then the current directory's repo."
        ),
        show_default=False,
    ),
]

JsonOpt = Annotated[bool, typer.Option("--json", help="Print JSON instead of a table.")]

SinceOpt = Annotated[
    Optional[str],
    typer.Option(
        metavar="DURATION|DATE",
        help=(
            "Only show items from this point on: 30m, 12h, 7d, 2w, 1y, "
            "or an ISO date/datetime (UTC unless an offset is given)."
        ),
        show_default=False,
    ),
]


@dataclass
class AppState:
    """Stored on the Typer context by the root callback.

    `config` is injected by tests; otherwise it is loaded lazily from `config_path`.
    """

    config: Config | None = None
    config_path: Path | None = None


def resolve_repo(ctx: typer.Context, repo: str | None) -> str | None:
    """Pick the repo: the argument, else the config's default_repo, else None (gh's cwd).

    A bad config file prints `error: <msg>` to stderr and exits 1. The file is only
    read when no repo argument was given.
    """
    if repo is not None:
        return repo
    state = ctx.find_object(AppState)
    if state is None:
        return None
    try:
        if state.config is None:
            state.config = load_config(state.config_path) if state.config_path else Config()
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    return state.config.default_repo


def since_cutoff(since: str | None, now: datetime) -> datetime | None:
    """Parse --since into a cutoff, or None if it wasn't given.

    A bad value raises typer.BadParameter: a usage error, exit 2, before gh runs.
    """
    if since is None:
        return None
    try:
        return parse_since(since, now)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="'--since'") from None


def fetch_or_exit(fn: Callable[..., T], /, *args: object, **kwargs: object) -> T:
    """Call a gh.list_* function; on GhError print `error: <msg>` to stderr and exit 1."""
    try:
        return fn(*args, **kwargs)
    except gh.GhError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None


def repo_title(repo: str | None, what: str, since: str | None = None) -> str:
    title = f"{repo or 'current repo'}: {what}"
    return f"{title} since {since.strip()}" if since else title
