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
