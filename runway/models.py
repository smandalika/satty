"""Core data types shared by every source and scorer."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


@dataclass
class Posting:
    """One internship posting, normalized across every source."""

    company: str
    title: str
    url: str
    source: str
    posted_at: datetime
    locations: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    category: str = ""
    sponsorship: str = ""
    degrees: list[str] = field(default_factory=list)
    description: str = ""
    source_id: str = ""

    @property
    def key(self) -> str:
        """Stable identity used for de-duplication across sources.

        Deliberately not the source's own id: the same job shows up in
        several feeds with different ids, and we only want to alert once.
        """
        canonical = f"{_slug(self.company)}|{_slug(self.title)}|{self._url_key()}"
        return hashlib.sha1(canonical.encode()).hexdigest()[:16]

    def _url_key(self) -> str:
        # Strip query strings and tracking params so the same posting linked
        # from two feeds collapses to one key.
        return re.sub(r"[?#].*$", "", self.url or "").rstrip("/").lower()

    @property
    def age_hours(self) -> float:
        delta = datetime.now(timezone.utc) - self.posted_at
        return max(delta.total_seconds() / 3600.0, 0.0)

    @property
    def haystack(self) -> str:
        """Everything a keyword matcher should look at, lowercased."""
        parts = [self.title, self.category, self.company, self.description]
        parts.extend(self.locations)
        parts.extend(self.terms)
        return " ".join(p for p in parts if p).lower()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["posted_at"] = self.posted_at.isoformat()
        d["key"] = self.key
        return d


@dataclass
class Scored:
    """A posting plus the reasoning behind its score."""

    posting: Posting
    total: float
    sophomore_fit: float
    profile_fit: float
    freshness: float
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def tier(self) -> str:
        if self.total >= 70:
            return "apply-now"
        if self.total >= 50:
            return "strong"
        if self.total >= 32:
            return "worth-a-shot"
        return "long-shot"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.posting.to_dict(),
            "total": round(self.total, 1),
            "sophomore_fit": round(self.sophomore_fit, 1),
            "profile_fit": round(self.profile_fit, 1),
            "freshness": round(self.freshness, 1),
            "tier": self.tier,
            "reasons": self.reasons,
            "blockers": self.blockers,
        }
