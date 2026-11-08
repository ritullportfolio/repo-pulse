from __future__ import annotations

import json
from datetime import timedelta

from typer.testing import CliRunner

from repo_pulse.cli import create_app
from tests.conftest import NOW, FakeGh

runner = CliRunner()


def invoke(fake: FakeGh, clock, *args: str):
    return runner.invoke(create_app(runner=fake, clock=clock), list(args))


def test_prs_table_shows_rows_with_ages_from_fixed_clock(fake_gh, fixed_clock) -> None:
    result = invoke(fake_gh, fixed_clock, "prs", "acme/widgets")
    assert result.exit_code == 0, result.output
    out = result.output
    for expected in ("42", "alice", "2d", "approved",
                     "41", "bob", "3h", "review required",
                     "40", "ghost", "6w"):
        assert expected in out


def test_ages_follow_the_clock_not_the_calendar(fake_gh) -> None:
    # Same data, clock moved forward 30 days: #41 (3h old at NOW) becomes 4w.
    later = lambda: NOW + timedelta(days=30)  # noqa: E731
    result = invoke(fake_gh, later, "prs", "acme/widgets", "--json")
    ages = {row["number"]: row["age"] for row in json.loads(result.output)}
    assert ages == {42: "4w", 41: "4w", 40: "10w"}


def test_prs_json_output(fake_gh, fixed_clock) -> None:
    result = invoke(fake_gh, fixed_clock, "prs", "acme/widgets", "--json")
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows[0] == {
        "number": 42,
        "title": "Add retry to fetcher",
        "author": "alice",
        "created_at": "2026-01-13T12:00:00+00:00",
        "age_seconds": 2 * 24 * 3600,
        "age": "2d",
        "review_decision": "APPROVED",
        "url": "https://github.com/acme/widgets/pull/42",
    }
    assert rows[2]["author"] == "ghost"
    assert rows[2]["review_decision"] is None


def test_prs_passes_options_to_gh(fake_gh, fixed_clock) -> None:
    result = invoke(fake_gh, fixed_clock, "prs", "acme/widgets", "--state", "merged", "--limit", "3")
    assert result.exit_code == 0, result.output
    call = fake_gh.calls[0]
    assert call[call.index("--state") + 1] == "merged"
    assert call[call.index("--limit") + 1] == "3"


def test_prs_defaults_to_current_repo(fake_gh, fixed_clock) -> None:
    result = invoke(fake_gh, fixed_clock, "prs")
    assert result.exit_code == 0, result.output
    assert "--repo" not in fake_gh.calls[0]


def test_prs_empty_list(fixed_clock) -> None:
    result = invoke(FakeGh(stdout="[]"), fixed_clock, "prs", "acme/widgets")
    assert result.exit_code == 0
    assert "No pull requests found" in result.output


def test_prs_rejects_invalid_state(fake_gh, fixed_clock) -> None:
    result = invoke(fake_gh, fixed_clock, "prs", "acme/widgets", "--state", "bogus")
    assert result.exit_code != 0
    assert fake_gh.calls == []


def test_prs_rejects_zero_limit(fake_gh, fixed_clock) -> None:
    result = invoke(fake_gh, fixed_clock, "prs", "acme/widgets", "--limit", "0")
    assert result.exit_code != 0
    assert fake_gh.calls == []


def test_prs_gh_failure_exits_1_with_clean_message(fixed_clock) -> None:
    fake = FakeGh(returncode=1, stderr="GraphQL: Could not resolve to a Repository with the name 'acme/nope'.")
    result = invoke(fake, fixed_clock, "prs", "acme/nope")
    assert result.exit_code == 1
    assert "error: gh failed: GraphQL: Could not resolve" in result.output
    assert "Traceback" not in result.output


def test_prs_gh_not_installed(fixed_clock) -> None:
    result = invoke(FakeGh(raises=FileNotFoundError()), fixed_clock, "prs", "acme/widgets")
    assert result.exit_code == 1
    assert "gh CLI was not found" in result.output
