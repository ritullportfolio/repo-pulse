"""The only module that runs the `gh` CLI.

Every call goes through a *runner*: a function that takes the argument list
(without the leading "gh") and returns a CompletedProcess. The default runner
shells out to the real binary; tests pass a fake one.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

from repo_pulse.models import PullRequest

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]

PR_FIELDS = ("number", "title", "author", "createdAt", "reviewDecision", "url")


class GhError(Exception):
    """A gh invocation failed; the message is safe to show the user."""


def default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def run_gh(args: list[str], runner: Runner | None = None) -> Any:
    """Run `gh <args>` and return its stdout parsed as JSON."""
    runner = runner or default_runner
    try:
        proc = runner(args)
    except FileNotFoundError:
        raise GhError(
            "the gh CLI was not found on PATH. Install it from https://cli.github.com"
        ) from None

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if "gh auth login" in stderr or "not logged" in stderr.lower():
            raise GhError("gh is not logged in. Run: gh auth login")
        raise GhError(f"gh failed: {stderr}" if stderr else f"gh exited with code {proc.returncode}")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"could not parse gh output as JSON: {exc}") from None


def list_prs(
    repo: str | None,
    state: str = "open",
    limit: int = 20,
    runner: Runner | None = None,
) -> list[PullRequest]:
    """List pull requests. With repo=None, gh uses the current directory's repo."""
    args = ["pr", "list"]
    if repo:
        args += ["--repo", repo]
    args += ["--state", state, "--limit", str(limit), "--json", ",".join(PR_FIELDS)]

    data = run_gh(args, runner)
    if not isinstance(data, list):
        raise GhError("unexpected gh output: expected a JSON list of pull requests")
    return [PullRequest.from_gh(item) for item in data]
