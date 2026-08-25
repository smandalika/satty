"""The community-maintained aggregate feeds.

These are the reason this works at all. Volunteers and scrapers push new
postings into these repos within minutes of them going live, which is the
same freshness edge a paid tracker sells.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Posting
from .base import Source, http_json

RAW = "https://raw.githubusercontent.com/{repo}/{branch}/.github/scripts/listings.json"

# repo, branch, and a label for the digest.
GITHUB_FEEDS = [
    {"repo": "SimplifyJobs/Summer2027-Internships", "label": "simplify-2027"},
    {"repo": "vanshb03/Summer2027-Internships", "label": "vansh-2027"},
]
# Note: SimplifyJobs serves byte-identical listings.json from its 2026 and 2027
# repos, so adding the 2026 one buys nothing and costs an 11MB download.


class GithubListingsSource(Source):
    def __init__(self, repo: str, branch: str = "dev", label: str = ""):
        self.repo = repo
        self.branch = branch
        self.name = label or repo

    def fetch(self) -> list[Posting]:
        rows = http_json(RAW.format(repo=self.repo, branch=self.branch))
        if not isinstance(rows, list):
            return []
        return [p for p in (self._parse(r) for r in rows) if p is not None]

    def _parse(self, row: dict) -> Posting | None:
        # The feeds mark filled/pulled roles rather than deleting them.
        if not row.get("active", True) or not row.get("is_visible", True):
            return None
        url = row.get("url") or ""
        company = (row.get("company_name") or "").strip()
        title = (row.get("title") or "").strip()
        if not (url and company and title):
            return None

        ts = row.get("date_posted") or row.get("date_updated") or 0
        try:
            posted = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

        # Schemas differ slightly between the two repos: one uses `terms`
        # (a list), the other a single `season` string.
        terms = row.get("terms") or []
        if not terms and row.get("season"):
            terms = [str(row["season"])]

        return Posting(
            company=company,
            title=title,
            url=url,
            source=self.name,
            posted_at=posted,
            locations=[str(x) for x in (row.get("locations") or [])],
            terms=[str(t) for t in terms],
            category=str(row.get("category") or ""),
            sponsorship=str(row.get("sponsorship") or ""),
            degrees=[str(d) for d in (row.get("degrees") or [])],
            source_id=str(row.get("id") or ""),
        )
