"""Plain data types built from gh's JSON output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    author: str
    created_at: datetime
    review_decision: str | None  # APPROVED, CHANGES_REQUESTED, REVIEW_REQUIRED or None
    url: str

    @classmethod
    def from_gh(cls, data: dict[str, Any]) -> PullRequest:
        # Deleted accounts come back as author: null.
        author = (data.get("author") or {}).get("login") or "ghost"
        return cls(
            number=int(data["number"]),
            title=data["title"],
            author=author,
            created_at=datetime.fromisoformat(data["createdAt"]),
            # gh returns "" when no review decision applies.
            review_decision=data.get("reviewDecision") or None,
            url=data["url"],
        )


def _parse_optional_time(value: str | None) -> datetime | None:
    """Parse a gh timestamp, treating "" and Go's zero time (year 1) as missing."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return None if parsed.year == 1 else parsed


@dataclass(frozen=True)
class Release:
    tag: str
    name: str | None
    published_at: datetime | None  # None for drafts, which are never published
    created_at: datetime
    is_latest: bool
    is_prerelease: bool
    is_draft: bool

    @property
    def released_at(self) -> datetime:
        """When the release went out, falling back to creation time for drafts."""
        return self.published_at or self.created_at

    @classmethod
    def from_gh(cls, data: dict[str, Any]) -> Release:
        return cls(
            tag=data["tagName"],
            # Releases created without a title come back as name: "".
            name=data.get("name") or None,
            published_at=_parse_optional_time(data.get("publishedAt")),
            created_at=datetime.fromisoformat(data["createdAt"]),
            is_latest=bool(data.get("isLatest")),
            is_prerelease=bool(data.get("isPrerelease")),
            is_draft=bool(data.get("isDraft")),
        )
