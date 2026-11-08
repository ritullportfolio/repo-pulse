from __future__ import annotations

from datetime import datetime, timezone

from repo_pulse.models import PullRequest

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
