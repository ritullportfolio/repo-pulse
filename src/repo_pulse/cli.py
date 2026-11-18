"""Typer entry point. Kept thin: build the app and register every report.

Each report lives in its own module under `repo_pulse.reports` and is listed in
`REPORTS`. `create_app` takes the gh runner and the clock as parameters so tests
can inject fakes; the module-level `app` uses the real ones.
"""

from __future__ import annotations

from typing import Annotated

import typer

from repo_pulse import __version__, gh
from repo_pulse.metrics import Clock, utc_now
from repo_pulse.reports import REPORTS


def _print_version(value: bool) -> None:
    # Module-level, not inside create_app: with `from __future__ import
    # annotations`, Typer resolves the Annotated callback against module globals.
    if value:
        typer.echo(f"repo-pulse {__version__}")
        raise typer.Exit()


def create_app(runner: gh.Runner | None = None, clock: Clock = utc_now) -> typer.Typer:
    app = typer.Typer(
        help="Quick health reports for GitHub repositories, powered by the gh CLI.",
        no_args_is_help=True,
        add_completion=False,
    )

    @app.callback()
    def main(
        version: Annotated[
            bool,
            typer.Option(
                "--version",
                callback=_print_version,
                is_eager=True,
                help="Show the version and exit.",
            ),
        ] = False,
    ) -> None:
        """Quick health reports for GitHub repositories, powered by the gh CLI."""

    for report in REPORTS:
        report.register(app, runner=runner, clock=clock)

    return app


app = create_app()
