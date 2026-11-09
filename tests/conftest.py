from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

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
