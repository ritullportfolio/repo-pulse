from __future__ import annotations

from datetime import datetime, timezone

from repo_pulse.models import PullRequest, Release

BASE = {
    "number": 7,
    "title": "Something",
    "author": {"login": "carol"},
    "createdAt": "2026-01-01T00:00:00Z",
    "reviewDecision": "CHANGES_REQUESTED",
    "url": "https://example.test/pull/7",
}


def test_from_gh_maps_fields() -> None:
    pr = PullRequest.from_gh(BASE)
    assert pr.number == 7
    assert pr.author == "carol"
    assert pr.review_decision == "CHANGES_REQUESTED"
    assert pr.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_from_gh_null_author_becomes_ghost() -> None:
    assert PullRequest.from_gh({**BASE, "author": None}).author == "ghost"


def test_from_gh_empty_review_decision_becomes_none() -> None:
    assert PullRequest.from_gh({**BASE, "reviewDecision": ""}).review_decision is None


RELEASE = {
    "tagName": "v1.2.3",
    "name": "Widgets 1.2.3",
    "publishedAt": "2026-01-02T00:00:00Z",
    "createdAt": "2026-01-01T00:00:00Z",
    "isLatest": True,
    "isPrerelease": False,
    "isDraft": False,
}


def test_release_from_gh_maps_fields() -> None:
    r = Release.from_gh(RELEASE)
    assert r.tag == "v1.2.3"
    assert r.name == "Widgets 1.2.3"
    assert r.published_at == datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert r.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert (r.is_latest, r.is_prerelease, r.is_draft) == (True, False, False)
    assert r.released_at == r.published_at


def test_release_from_gh_empty_name_becomes_none() -> None:
    assert Release.from_gh({**RELEASE, "name": ""}).name is None


def test_release_from_gh_zero_published_at_becomes_none() -> None:
    # gh reports unpublished drafts with Go's zero time.
    r = Release.from_gh({**RELEASE, "publishedAt": "0001-01-01T00:00:00Z", "isDraft": True})
    assert r.published_at is None
    assert r.released_at == r.created_at


def test_release_from_gh_empty_published_at_becomes_none() -> None:
    assert Release.from_gh({**RELEASE, "publishedAt": ""}).published_at is None
