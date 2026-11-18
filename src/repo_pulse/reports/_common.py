"""Pieces every report command shares: the repo argument, --json, and gh error handling.

Import these at module level in a report module. With `from __future__ import
annotations`, Typer resolves a command's annotations against its module's
globals, so annotation types defined inside `register()` would not be found.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Optional, TypeVar

import typer

from repo_pulse import gh

T = TypeVar("T")

RepoArg = Annotated[
    Optional[str],
    typer.Argument(
        metavar="[OWNER/REPO]",
        help="Repository to inspect. Defaults to the current directory's repo.",
        show_default=False,
    ),
]

JsonOpt = Annotated[bool, typer.Option("--json", help="Print JSON instead of a table.")]


def fetch_or_exit(fn: Callable[..., T], /, *args: object, **kwargs: object) -> T:
    """Call a gh.list_* function; on GhError print `error: <msg>` to stderr and exit 1."""
    try:
        return fn(*args, **kwargs)
    except gh.GhError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None


def repo_title(repo: str | None, what: str) -> str:
    return f"{repo or 'current repo'}: {what}"
