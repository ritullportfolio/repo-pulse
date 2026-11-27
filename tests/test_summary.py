"""The `summary` command: metrics.summarize, the RepoSummary model and the CLI."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from typer.testing import CliRunner

from repo_pulse.cli import create_app
from repo_pulse.config import Config
from repo_pulse.metrics import summarize
from repo_pulse.models import PullRequest, Release, RepoSummary
from tests.conftest import NOW, FakeGh, RoutedFakeGh

runner = CliRunner()

PR_ARGS = ["pr", "list", "--repo", "acme/widgets", "--state", "open", "--limit", "100",
           "--json", "number,title,author,createdAt,reviewDecision,url"]
RELEASE_ARGS = ["release", "list", "--repo", "acme/widgets", "--limit", "20",
                "--json", "tagName,name,publishedAt,createdAt,isLatest,isPrerelease,isDraft"]


def invoke(fake, clock, *args: str, config: Config | None = None):
    return runner.invoke(create_app(runner=fake, clock=clock, config_override=config), list(args))


def routed(prs: str = "[]", releases: str = "[]") -> RoutedFakeGh:
    return RoutedFakeGh({"pr list": FakeGh(stdout=prs), "release list": FakeGh(stdout=releases)})


def _pr(number: int, hours_old: int, decision: str | None = None) -> PullRequest:
    return PullRequest(number, f"PR {number}", "alice", NOW - timedelta(hours=hours_old),
                       decision, f"https://example.test/{number}")


def _release(tag: str, hours_old: int, *, latest=False, pre=False, draft=False) -> Release:
    when = NOW - timedelta(hours=hours_old)
    return Release(tag, None, None if draft else when, when, latest, pre, draft)


# --- metrics.summarize ------------------------------------------------------


def test_summarize_empty_repo() -> None:
    assert summarize([], []) == RepoSummary(0, 0, None, None, None)


def test_summarize_counts_prs_and_finds_the_oldest() -> None:
    prs = [_pr(1, 5, "REVIEW_REQUIRED"), _pr(2, 50, "APPROVED"), _pr(3, 1, None),
           _pr(4, 2, "REVIEW_REQUIRED")]
    result = summarize(prs, [])
    assert result.open_prs == 4
    assert result.prs_needing_review == 2  # None (no review policy) doesn't count
    assert result.oldest_open_pr.number == 2


def test_summarize_picks_latest_and_the_newest_newer_prerelease_or_draft() -> None:
    releases = [
        _release("v3-draft", 1, draft=True),
        _release("v3-rc2", 5, pre=True),
        _release("v2", 10, latest=True),
        _release("v2-rc1", 20, pre=True),  # older than latest: ignored
    ]
    result = summarize([], releases)
    assert result.latest_release.tag == "v2"
    assert result.newer_unreleased.tag == "v3-draft"


def test_summarize_no_newer_unreleased_when_latest_is_newest() -> None:
    releases = [_release("v2", 1, latest=True), _release("v2-rc1", 20, pre=True)]
    assert summarize([], releases).newer_unreleased is None


def test_summarize_latest_release_ignores_cutoff() -> None:
    releases = [_release("v2", 24 * 400, latest=True)]  # over a year old
    result = summarize([], releases, cutoff=NOW - timedelta(days=7))
    assert result.latest_release.tag == "v2"


def test_summarize_cutoff_still_limits_newer_prereleases() -> None:
    releases = [
        _release("v3-rc2", 2, pre=True),
        _release("v3-rc1", 24 * 10, pre=True),  # newer than v2, but before the cutoff
        _release("v2", 24 * 30, latest=True),
    ]
    week = NOW - timedelta(days=7)
    assert summarize([], releases, cutoff=week).newer_unreleased.tag == "v3-rc2"
    assert summarize([], releases[1:], cutoff=week).newer_unreleased is None
    assert summarize([], releases[1:]).newer_unreleased.tag == "v3-rc1"


def test_summary_since_keeps_a_year_old_latest_release(fixed_clock) -> None:
    old = [{"tagName": "v1.0.0", "name": "", "createdAt": "2025-01-01T10:00:00Z",
            "publishedAt": "2025-01-01T12:00:00Z", "isLatest": True,
            "isPrerelease": False, "isDraft": False}]
    fake = routed(releases=json.dumps(old))
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--since", "7d")
    assert result.exit_code == 0, result.output
    assert "v1.0.0 (1y)" in result.output


def test_summarize_without_a_latest_release_reports_any_prerelease() -> None:
    result = summarize([], [_release("v1-rc1", 3, pre=True), _release("v1-beta", 9, pre=True)])
    assert result.latest_release is None
    assert result.newer_unreleased.tag == "v1-rc1"


# --- CLI --------------------------------------------------------------------


def test_summary_calls_pr_list_then_release_list(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 0, result.output
    assert fake_gh_summary.calls == [PR_ARGS, RELEASE_ARGS]


def test_summary_table(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 0, result.output
    out = result.output
    assert "acme/widgets: summary" in out
    for expected in ("Open PRs", "3", "Needing review", "1",
                     "#40 Old abandoned branch (6w)",
                     "v2.1.0 (3d)",
                     "v2.2.0 draft (30m)"):
        assert expected in out


def test_summary_json_is_one_object(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets", "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["open_prs"] == 3
    assert data["open_prs_limit_reached"] is False
    assert data["prs_needing_review"] == 1
    assert data["oldest_open_pr"] == {
        "number": 40,
        "title": "Old abandoned branch",
        "author": "ghost",
        "created_at": "2025-12-01T12:00:00+00:00",
        "age_seconds": 45 * 24 * 3600,
        "age": "6w",
        "url": "https://github.com/acme/widgets/pull/40",
    }
    assert data["latest_release"]["tag"] == "v2.1.0"
    assert data["latest_release"]["status"] == "latest"
    assert data["latest_release"]["age"] == "3d"
    assert data["newer_unreleased"]["tag"] == "v2.2.0"
    assert data["newer_unreleased"]["status"] == "draft"
    assert data["newer_unreleased"]["published_at"] is None


def test_summary_empty_repo(fixed_clock) -> None:
    result = invoke(routed(), fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 0, result.output
    assert "Open PRs" in result.output
    assert "-" in result.output


def test_summary_empty_repo_json(fixed_clock) -> None:
    result = invoke(routed(), fixed_clock, "summary", "acme/widgets", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "open_prs": 0,
        "open_prs_limit_reached": False,
        "prs_needing_review": 0,
        "oldest_open_pr": None,
        "latest_release": None,
        "newer_unreleased": None,
    }


def test_summary_limit_reached_shows_plus(pr_list_json, release_list_json, fixed_clock) -> None:
    fake = routed(pr_list_json, release_list_json)
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "3")
    assert result.exit_code == 0, result.output
    assert "3+" in result.output
    assert fake.calls[0][fake.calls[0].index("--limit") + 1] == "3"
    data = json.loads(invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "3",
                             "--json").output)
    assert data["open_prs_limit_reached"] is True


def test_summary_rejects_zero_limit(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets", "--limit", "0")
    assert result.exit_code == 2
    assert fake_gh_summary.calls == []


def test_summary_defaults_to_current_repo(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary")
    assert result.exit_code == 0, result.output
    assert all("--repo" not in call for call in fake_gh_summary.calls)
    assert "current repo: summary" in result.output


def test_summary_uses_config_default_repo_for_both_calls(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary",
                    config=Config(default_repo="cli/cli"))
    assert result.exit_code == 0, result.output
    for call in fake_gh_summary.calls:
        assert call[call.index("--repo") + 1] == "cli/cli"
    assert "cli/cli: summary" in result.output


def test_summary_argument_overrides_config(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets",
                    config=Config(default_repo="cli/cli"))
    assert result.exit_code == 0, result.output
    assert fake_gh_summary.calls == [PR_ARGS, RELEASE_ARGS]


def test_summary_invalid_config_is_a_clean_error(fake_gh_summary, fixed_clock, tmp_path) -> None:
    path = tmp_path / "c.toml"
    path.write_text("default_repo = [oops\n")
    result = runner.invoke(create_app(runner=fake_gh_summary, clock=fixed_clock),
                           ["--config", str(path), "summary"])
    assert result.exit_code == 1
    assert "error: invalid TOML" in result.output
    assert fake_gh_summary.calls == []


@pytest.mark.parametrize("failing", ["pr list", "release list"])
def test_summary_gh_failure_exits_1(failing, pr_list_json, release_list_json, fixed_clock) -> None:
    fake = routed(pr_list_json, release_list_json)
    fake.routes[failing] = FakeGh(returncode=1, stderr="HTTP 502: Bad Gateway")
    result = invoke(fake, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 1
    assert "error: gh failed: HTTP 502: Bad Gateway" in result.output
    assert "Traceback" not in result.output
    assert "Open PRs" not in result.output  # no partial summary


def test_summary_pr_failure_skips_release_call(fixed_clock) -> None:
    fake = routed()
    fake.routes["pr list"] = FakeGh(returncode=1, stderr="boom")
    invoke(fake, fixed_clock, "summary", "acme/widgets")
    assert [call[:2] for call in fake.calls] == [["pr", "list"]]


def test_summary_gh_not_installed(fixed_clock) -> None:
    fake = RoutedFakeGh({"pr list": FakeGh(raises=FileNotFoundError())})
    result = invoke(fake, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 1
    assert "error: the gh CLI was not found" in result.output


def test_summary_since_filters_prs_but_not_the_latest_release(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets", "--since", "1d",
                    "--json")
    assert result.exit_code == 0, result.output
    pr_call = fake_gh_summary.calls[0]
    assert pr_call[pr_call.index("--search") + 1] == "created:>=2026-01-14"
    data = json.loads(result.output)
    assert data["open_prs"] == 1  # only #41 (3h old)
    assert data["oldest_open_pr"]["number"] == 41
    # v2.1.0 is 3d old, outside the 1d window, but is still the current release.
    assert data["latest_release"]["tag"] == "v2.1.0"
    assert data["latest_release"]["age"] == "3d"
    assert data["newer_unreleased"]["tag"] == "v2.2.0"


def test_summary_since_shows_in_title(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets", "--since", "1d")
    assert "acme/widgets: summary since 1d" in result.output


@pytest.mark.parametrize("value", ["soon", "0d", "-5d"])
def test_summary_invalid_since_is_a_usage_error_before_gh_runs(value, fixed_clock) -> None:
    fake = routed()
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--since", value)
    assert result.exit_code == 2
    assert "Invalid value for '--since'" in result.output
    assert fake.calls == []
