from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from repo_pulse import gh
from tests.conftest import FakeGh

FIELDS = "number,title,author,createdAt,reviewDecision,url"
RELEASE_FIELDS = "tagName,name,publishedAt,createdAt,isLatest,isPrerelease,isDraft"


def test_list_releases_builds_expected_command(fake_gh_releases: FakeGh) -> None:
    gh.list_releases("acme/widgets", limit=5, runner=fake_gh_releases)
    assert fake_gh_releases.calls == [[
        "release", "list", "--repo", "acme/widgets",
        "--limit", "5", "--json", RELEASE_FIELDS,
    ]]


def test_list_releases_without_repo_omits_repo_flag(fake_gh_releases: FakeGh) -> None:
    gh.list_releases(None, runner=fake_gh_releases)
    assert "--repo" not in fake_gh_releases.calls[0]


def test_list_releases_parses_fixture(fake_gh_releases: FakeGh) -> None:
    releases = gh.list_releases("acme/widgets", runner=fake_gh_releases)
    assert [r.tag for r in releases] == ["v2.2.0", "v2.2.0-rc.1", "v2.1.0", "v1.0.0"]
    assert releases[2].is_latest
    assert releases[0].is_draft


def test_list_releases_non_list_json_raises_gh_error() -> None:
    runner = FakeGh(stdout='{"oops": true}')
    with pytest.raises(gh.GhError, match="expected a JSON list of releases"):
        gh.list_releases("acme/widgets", runner=runner)


def test_list_prs_builds_expected_command(fake_gh: FakeGh) -> None:
    gh.list_prs("acme/widgets", state="merged", limit=5, runner=fake_gh)
    assert fake_gh.calls == [[
        "pr", "list", "--repo", "acme/widgets",
        "--state", "merged", "--limit", "5", "--json", FIELDS,
    ]]


def test_list_prs_cutoff_adds_created_search(fake_gh: FakeGh) -> None:
    cutoff = datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc)
    gh.list_prs("acme/widgets", limit=5, cutoff=cutoff, runner=fake_gh)
    assert fake_gh.calls == [[
        "pr", "list", "--repo", "acme/widgets",
        "--state", "open", "--limit", "5", "--json", FIELDS,
        "--search", "created:>=2026-01-08",
    ]]


def test_list_prs_cutoff_uses_the_utc_date() -> None:
    fake = FakeGh()
    # 02:00 on the 8th at UTC+05:30 is still the 7th in UTC.
    cutoff = datetime(2026, 1, 8, 2, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    gh.list_prs(None, cutoff=cutoff, runner=fake)
    assert fake.calls[0][-2:] == ["--search", "created:>=2026-01-07"]


def test_list_prs_without_cutoff_has_no_search(fake_gh: FakeGh) -> None:
    gh.list_prs("acme/widgets", runner=fake_gh)
    assert "--search" not in fake_gh.calls[0]


def test_list_prs_without_repo_omits_repo_flag(fake_gh: FakeGh) -> None:
    gh.list_prs(None, runner=fake_gh)
    assert "--repo" not in fake_gh.calls[0]


def test_list_prs_parses_fixture(fake_gh: FakeGh) -> None:
    prs = gh.list_prs("acme/widgets", runner=fake_gh)
    assert [pr.number for pr in prs] == [42, 41, 40]
    assert prs[0].author == "alice"
    assert prs[0].review_decision == "APPROVED"


def test_missing_binary_raises_gh_error() -> None:
    runner = FakeGh(raises=FileNotFoundError("gh"))
    with pytest.raises(gh.GhError, match="not found"):
        gh.run_gh(["pr", "list"], runner)


def test_not_logged_in_raises_gh_error() -> None:
    runner = FakeGh(
        returncode=4,
        stderr="To get started with GitHub CLI, please run:  gh auth login",
    )
    with pytest.raises(gh.GhError, match="not logged in"):
        gh.run_gh(["pr", "list"], runner)


def test_unknown_repo_passes_gh_message_through() -> None:
    msg = "GraphQL: Could not resolve to a Repository with the name 'acme/nope'."
    runner = FakeGh(returncode=1, stderr=msg)
    with pytest.raises(gh.GhError, match="Could not resolve to a Repository"):
        gh.list_prs("acme/nope", runner=runner)


def test_nonzero_exit_with_empty_stderr() -> None:
    runner = FakeGh(returncode=2, stderr="")
    with pytest.raises(gh.GhError, match="exited with code 2"):
        gh.run_gh(["pr", "list"], runner)


def test_invalid_json_raises_gh_error() -> None:
    runner = FakeGh(stdout="not json")
    with pytest.raises(gh.GhError, match="could not parse"):
        gh.run_gh(["pr", "list"], runner)


def test_non_list_json_raises_gh_error() -> None:
    runner = FakeGh(stdout='{"oops": true}')
    with pytest.raises(gh.GhError, match="expected a JSON list"):
        gh.list_prs("acme/widgets", runner=runner)


def test_default_runner_does_not_use_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        raise FileNotFoundError

    monkeypatch.setattr(gh.subprocess, "run", fake_run)
    with pytest.raises(gh.GhError):
        gh.run_gh(["pr", "list"])
    assert captured["cmd"] == ["gh", "pr", "list"]
    assert not captured["kwargs"].get("shell", False)
