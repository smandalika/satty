"""Ashby public job board API — no key needed."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Posting
from .base import Source, http_json
from .greenhouse import INTERNISH, strip_html

API = "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"


class AshbySource(Source):
    def __init__(self, board: str):
        self.board = board
        self.name = f"ashby:{board}"

    def fetch(self) -> list[Posting]:
        data = http_json(API.format(board=self.board))
        out = []
        for job in data.get("jobs", []) or []:
            title = (job.get("title") or "").strip()
            if not INTERNISH.search(title):
                continue
            published = job.get("publishedAt") or job.get("updatedAt") or ""
            try:
                dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now(timezone.utc)
            loc = job.get("location") or ""
            out.append(
                Posting(
                    company=data.get("name") or self.board.title(),
                    title=title,
                    url=job.get("jobUrl") or job.get("applyUrl") or "",
                    source=self.name,
                    posted_at=dt.astimezone(timezone.utc),
                    locations=[loc] if loc else [],
                    category=job.get("department") or "",
                    description=strip_html(job.get("descriptionHtml") or job.get("descriptionPlain", "")),
                    source_id=str(job.get("id") or ""),
                )
            )
        return out
