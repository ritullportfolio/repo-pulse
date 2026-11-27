from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import typer.rich_utils

FIXTURES = Path(__file__).parent / "fixtures"

# Fixed "now" for every test: ages are computed relative to this, never the real clock.
NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


class FakeGh:
    """Stands in for the gh binary. Records every call and returns a canned result."""

    def __init__(self, stdout: str = "[]", stderr: str = "", returncode: int = 0,
                 raises: Exception | None = None) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.raises = raises
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(
            ["gh", *args], self.returncode, stdout=self.stdout, stderr=self.stderr
        )


class RoutedFakeGh:
    """Routes each gh call to a FakeGh by its subcommand, e.g. "pr list" or "release view".

    For commands like `summary` that call gh more than once. A route may be a list of
    FakeGh, used one per call in order, for a subcommand called more than once. `calls`
    records every call in order across all routes. An unrouted subcommand goes to
    `default`, or fails the test if there is none.
    """

    def __init__(self, routes: dict[str, FakeGh | list[FakeGh]],
                 default: FakeGh | None = None) -> None:
        self.routes = routes
        self.default = default
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        key = " ".join(args[:2])
        route = self.routes.get(key, self.default)
        if isinstance(route, list):
            if not route:
                raise AssertionError(f"more gh calls than expected: gh {' '.join(args)}")
            route = route.pop(0)
        if route is None:
            raise AssertionError(f"unexpected gh call: gh {' '.join(args)}")
        return route(args)


def no_release_gh() -> FakeGh:
    """What `gh release view` (no tag) does in a repo without releases."""
    return FakeGh(returncode=1, stderr="release not found")


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never let a test see the developer's own repo-pulse config.

    Without this, a real ~/.config/repo-pulse/config.toml (or $XDG_CONFIG_HOME or
    $REPO_PULSE_CONFIG) would change which repo the CLI tests ask gh for.
    """
    monkeypatch.delenv("REPO_PULSE_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))


# Env vars that make Typer/rich emit ANSI colour codes even when output isn't a TTY.
_COLOUR_ENV = ("GITHUB_ACTIONS", "FORCE_COLOR", "PY_COLORS", "TTY_COMPATIBLE", "TTY_INTERACTIVE")


@pytest.fixture(autouse=True)
def _plain_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI output free of ANSI colour codes, so string assertions work in CI.

    GitHub Actions sets GITHUB_ACTIONS=true. Typer reads that once at import time into
    typer.rich_utils.FORCE_TERMINAL and colours its usage errors, so unsetting the
    env var alone is too late: patch the constant too.
    """
    for name in _COLOUR_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", False)


@pytest.fixture
def pr_list_json() -> str:
    return (FIXTURES / "pr_list.json").read_text()


@pytest.fixture
def fake_gh(pr_list_json: str) -> FakeGh:
    return FakeGh(stdout=pr_list_json)


@pytest.fixture
def release_list_json() -> str:
    return (FIXTURES / "release_list.json").read_text()


@pytest.fixture
def fake_gh_releases(release_list_json: str) -> FakeGh:
    return FakeGh(stdout=release_list_json)


@pytest.fixture
def fixed_clock():
    return lambda: NOW


@pytest.fixture
def release_view_json() -> str:
    return (FIXTURES / "release_view.json").read_text()


@pytest.fixture
def fake_gh_summary(pr_list_json: str, release_list_json: str,
                    release_view_json: str) -> RoutedFakeGh:
    return RoutedFakeGh({
        "pr list": FakeGh(stdout=pr_list_json),
        "release view": FakeGh(stdout=release_view_json),
        "release list": FakeGh(stdout=release_list_json),
    })
