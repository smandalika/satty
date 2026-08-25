"""Lever public postings API — no key needed, descriptions included."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import Posting
from .base import Source, http_json
from .greenhouse import INTERNISH, strip_html

API = "https://api.lever.co/v0/postings/{board}?mode=json"


class LeverSource(Source):
    def __init__(self, board: str):
        self.board = board
        self.name = f"lever:{board}"

    def fetch(self) -> list[Posting]:
        out = []
        for job in http_json(API.format(board=self.board)) or []:
            title = (job.get("text") or "").strip()
            if not INTERNISH.search(title):
                continue
            try:
                dt = datetime.fromtimestamp(job.get("createdAt", 0) / 1000, tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                dt = datetime.now(timezone.utc)
            cats = job.get("categories") or {}
            loc = cats.get("location") or ""
            out.append(
                Posting(
                    company=self.board.replace("-", " ").title(),
                    title=title,
                    url=job.get("hostedUrl") or "",
                    source=self.name,
                    posted_at=dt,
                    locations=[loc] if loc else [],
                    category=cats.get("team") or "",
                    description=strip_html(job.get("descriptionPlain") or job.get("description", "")),
                    source_id=str(job.get("id") or ""),
                )
            )
        return out
