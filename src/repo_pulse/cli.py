"""Typer entry point. Kept thin: build the app and register every report.

Each report lives in its own module under `repo_pulse.reports` and is listed in
`REPORTS`. `create_app` takes the gh runner and the clock as parameters so tests
can inject fakes; the module-level `app` uses the real ones.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from repo_pulse import __version__, gh
from repo_pulse.config import Config, default_config_path
from repo_pulse.metrics import Clock, utc_now
from repo_pulse.reports import REPORTS
from repo_pulse.reports._common import AppState


def _print_version(value: bool) -> None:
    # Module-level, not inside create_app: with `from __future__ import
    # annotations`, Typer resolves the Annotated callback against module globals.
    if value:
        typer.echo(f"repo-pulse {__version__}")
        raise typer.Exit()


def create_app(
    runner: gh.Runner | None = None,
    clock: Clock = utc_now,
    config: Config | None = None,
) -> typer.Typer:
    """`config` is injected by tests; when None, the config file is read lazily."""
    app = typer.Typer(
        help="Quick health reports for GitHub repositories, powered by the gh CLI.",
        no_args_is_help=True,
        add_completion=False,
    )

    @app.callback()
    def main(
        ctx: typer.Context,
        config_file: Annotated[
            Optional[Path],
            typer.Option(
                "--config",
                envvar="REPO_PULSE_CONFIG",
                dir_okay=False,
                help=(
                    "Config file (TOML). Default: $XDG_CONFIG_HOME/repo-pulse/config.toml "
                    "or ~/.config/repo-pulse/config.toml."
                ),
                show_default=False,
            ),
        ] = None,
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
        ctx.obj = AppState(
            config=config,
            config_path=config_file or (None if config is not None else default_config_path()),
        )

    for report in REPORTS:
        report.register(app, runner=runner, clock=clock)

    return app


app = create_app()
