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
from tests.conftest import NOW, FakeGh, RoutedFakeGh, no_release_gh

runner = CliRunner()

PR_JSON = ["--json", "number,title,author,createdAt,reviewDecision,url"]
# --limit 100 (the default) fetches 101, to tell "exactly 100" from "more than 100".
PR_ARGS = ["pr", "list", "--repo", "acme/widgets", "--state", "open", "--limit", "101", *PR_JSON]
RELEASE_VIEW_ARGS = ["release", "view", "--repo", "acme/widgets",
                     "--json", "tagName,name,publishedAt,createdAt,isPrerelease,isDraft"]
RELEASE_ARGS = ["release", "list", "--repo", "acme/widgets", "--limit", "20",
                "--json", "tagName,name,publishedAt,createdAt,isLatest,isPrerelease,isDraft"]
ROW_LABELS = ("Open PRs", "Needing review", "Oldest open PR", "Latest release",
              "Newer pre-release/draft")


def invoke(fake, clock, *args: str, config: Config | None = None):
    return runner.invoke(create_app(runner=fake, clock=clock, config_override=config), list(args))


def routed(prs: str | list[str] = "[]", releases: str = "[]",
           latest: str | None = None) -> RoutedFakeGh:
    """A fake gh for summary. `prs` as a list answers successive `pr list` calls in order.
    With no `latest`, `gh release view` says the repo has no releases."""
    pr_route = [FakeGh(stdout=p) for p in prs] if isinstance(prs, list) else FakeGh(stdout=prs)
    return RoutedFakeGh({
        "pr list": pr_route,
        "release view": FakeGh(stdout=latest) if latest is not None else no_release_gh(),
        "release list": FakeGh(stdout=releases),
    })


def table_rows(output: str) -> dict[str, str]:
    """The summary table as {label: value}, so assertions compare whole cells.

    Substring checks can't fail here: "3" is in "v2.1.0 (3d)" and "-" is in the
    "Newer pre-release/draft" label.
    """
    rows = {}
    for line in output.splitlines():
        if line.startswith("│"):
            label, value = (cell.strip() for cell in line.strip().strip("│").split("│"))
            rows[label] = value
    assert tuple(rows) == ROW_LABELS, output
    return rows


def pr_json(number: int, created: str, decision: str = "") -> dict:
    return {"number": number, "title": f"PR {number}", "author": {"login": "alice"},
            "createdAt": created, "reviewDecision": decision,
            "url": f"https://github.com/acme/widgets/pull/{number}"}


def release_json(tag: str, published: str, *, pre: bool = False, latest: bool = False) -> dict:
    return {"tagName": tag, "name": "", "createdAt": published, "publishedAt": published,
            "isLatest": latest, "isPrerelease": pre, "isDraft": False}


def _pr(number: int, hours_old: int, decision: str | None = None) -> PullRequest:
    return PullRequest(number, f"PR {number}", "alice", NOW - timedelta(hours=hours_old),
                       decision, f"https://example.test/{number}")


def _release(tag: str, hours_old: int, *, latest=False, pre=False, draft=False) -> Release:
    when = NOW - timedelta(hours=hours_old)
    return Release(tag, None, None if draft else when, when, latest, pre, draft)


# --- metrics.summarize ------------------------------------------------------


def test_summarize_empty_repo() -> None:
    assert summarize([], None, []) == RepoSummary(0, 0, None, None, None)


def test_summarize_counts_prs_and_finds_the_oldest() -> None:
    prs = [_pr(1, 5, "REVIEW_REQUIRED"), _pr(2, 50, "APPROVED"), _pr(3, 1, None),
           _pr(4, 2, "REVIEW_REQUIRED")]
    result = summarize(prs, None, [])
    assert result.open_prs == 4
    assert result.prs_needing_review == 2  # None (no review policy) doesn't count
    assert result.oldest_open_pr.number == 2


def test_summarize_uses_a_given_oldest_pr_over_the_list() -> None:
    # A truncated list doesn't hold the oldest PR; the caller looks it up separately.
    older = _pr(9, 900)
    assert summarize([_pr(1, 5), _pr(2, 50)], None, [], oldest_open_pr=older).oldest_open_pr is older


def test_summarize_picks_the_newest_prerelease_or_draft_newer_than_latest() -> None:
    latest = _release("v2", 10, latest=True)
    releases = [
        _release("v3-draft", 1, draft=True),
        _release("v3-rc2", 5, pre=True),
        latest,
        _release("v2-rc1", 20, pre=True),  # older than latest: ignored
    ]
    result = summarize([], latest, releases)
    assert result.latest_release is latest
    assert result.newer_unreleased.tag == "v3-draft"


def test_summarize_no_newer_unreleased_when_latest_is_newest() -> None:
    latest = _release("v2", 1, latest=True)
    assert summarize([], latest, [latest, _release("v2-rc1", 20, pre=True)]).newer_unreleased is None


def test_summarize_latest_release_ignores_cutoff() -> None:
    latest = _release("v2", 24 * 400, latest=True)  # over a year old
    result = summarize([], latest, [], cutoff=NOW - timedelta(days=7))
    assert result.latest_release is latest


def test_summarize_cutoff_still_limits_newer_prereleases() -> None:
    latest = _release("v2", 24 * 30, latest=True)
    rc2 = _release("v3-rc2", 2, pre=True)
    rc1 = _release("v3-rc1", 24 * 10, pre=True)  # newer than v2, but before the cutoff
    week = NOW - timedelta(days=7)
    assert summarize([], latest, [rc2, rc1], cutoff=week).newer_unreleased is rc2
    assert summarize([], latest, [rc1], cutoff=week).newer_unreleased is None
    assert summarize([], latest, [rc1]).newer_unreleased is rc1


def test_summarize_without_a_latest_release_reports_any_prerelease() -> None:
    result = summarize([], None, [_release("v1-rc1", 3, pre=True), _release("v1-beta", 9, pre=True)])
    assert result.latest_release is None
    assert result.newer_unreleased.tag == "v1-rc1"


def test_summary_since_keeps_a_year_old_latest_release(fixed_clock) -> None:
    old = {"tagName": "v1.0.0", "name": "", "createdAt": "2025-01-01T10:00:00Z",
           "publishedAt": "2025-01-01T12:00:00Z", "isPrerelease": False, "isDraft": False}
    fake = routed(latest=json.dumps(old))
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--since", "7d")
    assert result.exit_code == 0, result.output
    assert table_rows(result.output)["Latest release"] == "v1.0.0 (1y)"


# --- CLI --------------------------------------------------------------------


def test_summary_gh_calls_in_order(fake_gh_summary, fixed_clock) -> None:
    # pr list first: for a repo that doesn't exist, `gh release view` only says
    # "release not found", which summary reads as "no releases yet".
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 0, result.output
    assert fake_gh_summary.calls == [PR_ARGS, RELEASE_VIEW_ARGS, RELEASE_ARGS]


def test_summary_table(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 0, result.output
    assert "acme/widgets: summary" in result.output
    assert table_rows(result.output) == {
        "Open PRs": "3",
        "Needing review": "1",
        "Oldest open PR": "#40 Old abandoned branch (6w)",
        "Latest release": "v2.1.0 (3d)",
        "Newer pre-release/draft": "v2.2.0 draft (30m)",
    }


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
    assert table_rows(result.output) == {
        "Open PRs": "0",
        "Needing review": "0",
        "Oldest open PR": "-",
        "Latest release": "-",
        "Newer pre-release/draft": "-",
    }


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


def test_summary_more_prs_than_limit_shows_plus(pr_list_json, fixed_clock) -> None:
    # The fixture has 3 PRs (newest first: #42, #41, #40), so --limit 2 is truncated.
    oldest = json.dumps([pr_json(40, "2025-12-01T12:00:00Z")])
    fake = routed([pr_list_json, oldest])
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "2")
    assert result.exit_code == 0, result.output
    rows = table_rows(result.output)
    assert rows["Open PRs"] == "2+"
    assert rows["Needing review"] == "1+"
    assert fake.calls[0][fake.calls[0].index("--limit") + 1] == "3"  # limit + 1

    fake = routed([pr_list_json, oldest])
    data = json.loads(invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "2",
                             "--json").output)
    assert data["open_prs"] == 2
    assert data["open_prs_limit_reached"] is True


# Finding 3: "N+" when the count is exact.


def test_summary_exactly_limit_prs_is_exact(pr_list_json, fixed_clock) -> None:
    fake = routed(pr_list_json)
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "3")
    assert result.exit_code == 0, result.output
    assert table_rows(result.output)["Open PRs"] == "3"
    assert fake.calls[0][fake.calls[0].index("--limit") + 1] == "4"
    assert [call[:2] for call in fake.calls].count(["pr", "list"]) == 1  # no oldest lookup


def test_summary_since_trimming_makes_the_count_exact(fixed_clock) -> None:
    # gh filters by date, so it returns #42 (2d old) for --since 1d. It's newest first,
    # so once one PR falls before the cutoff, every PR after the cutoff was seen.
    prs = json.dumps([pr_json(41, "2026-01-15T09:00:00Z", "REVIEW_REQUIRED"),
                      pr_json(42, "2026-01-13T12:00:00Z")])
    fake = routed(prs)
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "1",
                    "--since", "1d", "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["open_prs"] == 1
    assert data["open_prs_limit_reached"] is False
    assert data["oldest_open_pr"]["number"] == 41


# Finding 1: gh returns newest first, so a truncated list doesn't hold the oldest PR.


def test_summary_fetches_the_oldest_pr_when_the_list_is_truncated(fixed_clock) -> None:
    newest = json.dumps([pr_json(50, "2026-01-15T11:00:00Z"),
                         pr_json(49, "2026-01-15T10:00:00Z"),
                         pr_json(48, "2026-01-15T09:00:00Z")])
    oldest = json.dumps([pr_json(7, "2025-10-07T12:00:00Z")])
    fake = routed([newest, oldest])
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "2")
    assert result.exit_code == 0, result.output
    assert table_rows(result.output)["Oldest open PR"] == "#7 PR 7 (14w)"
    assert fake.calls[1] == ["pr", "list", "--repo", "acme/widgets", "--state", "open",
                             "--limit", "1", *PR_JSON, "--search", "sort:created-asc"]


def test_summary_oldest_pr_with_since_skips_prs_before_the_exact_cutoff(fixed_clock) -> None:
    # --since 1d is 2026-01-14T12:00Z. gh searches from midnight that day, so the
    # oldest-first lookup can start with PRs a few hours too old.
    newest = json.dumps([pr_json(50, "2026-01-15T11:00:00Z"),
                         pr_json(49, "2026-01-15T10:00:00Z"),
                         pr_json(48, "2026-01-15T09:00:00Z")])
    oldest = json.dumps([pr_json(30, "2026-01-14T06:00:00Z"),
                         pr_json(31, "2026-01-14T18:00:00Z")])
    fake = routed([newest, oldest])
    result = invoke(fake, fixed_clock, "summary", "acme/widgets", "--limit", "2",
                    "--since", "1d", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["oldest_open_pr"]["number"] == 31
    lookup = fake.calls[1]
    assert lookup[lookup.index("--search") + 1] == "created:>=2026-01-14 sort:created-asc"
    assert lookup[lookup.index("--limit") + 1] == "2"


# Finding 2: the latest release can sit behind more than RELEASE_LIMIT pre-releases.


def test_summary_finds_the_latest_release_behind_many_prereleases(
        release_view_json, fixed_clock) -> None:
    # A full RELEASE_LIMIT (20) of hourly nightlies: the latest release isn't among them.
    nightlies = [
        release_json(f"nightly-{h}", (NOW - timedelta(hours=h)).isoformat(), pre=True)
        for h in range(1, 21)
    ]
    fake = routed(releases=json.dumps(nightlies), latest=release_view_json)
    result = invoke(fake, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 0, result.output
    rows = table_rows(result.output)
    assert rows["Latest release"] == "v2.1.0 (3d)"
    assert rows["Newer pre-release/draft"] == "nightly-1 pre-release (1h)"


def test_summary_nightlies_older_than_latest_are_not_newer(release_view_json, fixed_clock) -> None:
    old_nightly = [release_json("nightly-old", "2026-01-01T00:00:00Z", pre=True)]
    fake = routed(releases=json.dumps(old_nightly), latest=release_view_json)
    result = invoke(fake, fixed_clock, "summary", "acme/widgets")
    assert table_rows(result.output)["Newer pre-release/draft"] == "-"


def test_summary_repo_without_releases_is_not_an_error(fixed_clock) -> None:
    fake = routed(releases=json.dumps([release_json("v1-rc1", "2026-01-15T09:00:00Z",
                                                    pre=True)]))
    result = invoke(fake, fixed_clock, "summary", "acme/widgets")
    assert result.exit_code == 0, result.output
    rows = table_rows(result.output)
    assert rows["Latest release"] == "-"
    assert rows["Newer pre-release/draft"] == "v1-rc1 pre-release (3h)"


def test_summary_rejects_zero_limit(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary", "acme/widgets", "--limit", "0")
    assert result.exit_code == 2
    assert fake_gh_summary.calls == []


def test_summary_defaults_to_current_repo(fake_gh_summary, fixed_clock) -> None:
    result = invoke(fake_gh_summary, fixed_clock, "summary")
    assert result.exit_code == 0, result.output
    assert all("--repo" not in call for call in fake_gh_summary.calls)
    assert "current repo: summary" in result.output


def test_summary_uses_config_default_repo_for_every_call(fake_gh_summary, fixed_clock) -> None:
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
    assert fake_gh_summary.calls == [PR_ARGS, RELEASE_VIEW_ARGS, RELEASE_ARGS]


def test_summary_invalid_config_is_a_clean_error(fake_gh_summary, fixed_clock, tmp_path) -> None:
    path = tmp_path / "c.toml"
    path.write_text("default_repo = [oops\n")
    result = runner.invoke(create_app(runner=fake_gh_summary, clock=fixed_clock),
                           ["--config", str(path), "summary"])
    assert result.exit_code == 1
    assert "error: invalid TOML" in result.output
    assert fake_gh_summary.calls == []


@pytest.mark.parametrize("failing", ["pr list", "release view", "release list"])
def test_summary_gh_failure_exits_1(failing, pr_list_json, release_list_json,
                                    release_view_json, fixed_clock) -> None:
    fake = routed(pr_list_json, release_list_json, release_view_json)
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
