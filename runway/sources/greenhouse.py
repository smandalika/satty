"""Greenhouse public job board API — no key needed.

Worth the extra request per company: `content=true` returns the full job
description, which is the only place the real eligibility language ("open to
students in any year", "must be graduating in 2027") ever appears.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from ..models import Posting
from .base import Source, http_json

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
INTERNISH = re.compile(r"intern|co-?op|university|student|new ?grad|apprentice", re.I)


def strip_html(raw: str) -> str:
    text = html.unescape(raw or "")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class GreenhouseSource(Source):
    def __init__(self, board: str):
        self.board = board
        self.name = f"greenhouse:{board}"

    def fetch(self) -> list[Posting]:
        data = http_json(API.format(board=self.board))
        out = []
        for job in data.get("jobs", []) or []:
            title = (job.get("title") or "").strip()
            if not INTERNISH.search(title):
                continue
            posted = job.get("updated_at") or job.get("first_published") or ""
            try:
                dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now(timezone.utc)
            loc = (job.get("location") or {}).get("name") or ""
            out.append(
                Posting(
                    company=self.board.replace("-", " ").title(),
                    title=title,
                    url=job.get("absolute_url") or "",
                    source=self.name,
                    posted_at=dt.astimezone(timezone.utc),
                    locations=[loc] if loc else [],
                    description=strip_html(job.get("content", "")),
                    source_id=str(job.get("id") or ""),
                )
            )
        return out
