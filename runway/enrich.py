"""Second pass: go get the actual job description.

The aggregate feeds only carry a title, and a title never says "open to
students in any year" or "must be graduating in 2027". That sentence is the
single most useful thing for deciding whether a sophomore should bother, and
it only exists in the posting body.

Roughly a quarter of feed postings live on an ATS with a free public API, so
for those we can fetch the real text. We only do it for postings that already
look promising — enriching two thousand rows to rank fifteen would be rude to
the APIs and slow for you.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Posting
from .sources.base import SourceError, http_json
from .sources.greenhouse import strip_html

log = logging.getLogger("runway.enrich")

GREENHOUSE = re.compile(r"(?:job-)?boards\.greenhouse\.io/([\w-]+)/jobs/(\d+)", re.I)
LEVER = re.compile(r"jobs\.lever\.co/([\w-]+)/([\w-]+)", re.I)
ASHBY = re.compile(r"jobs\.ashbyhq\.com/([\w-]+)/([\w-]+)", re.I)


def _greenhouse(board: str, job_id: str) -> str:
    data = http_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}")
    return strip_html(data.get("content", ""))


def _lever(board: str, job_id: str) -> str:
    data = http_json(f"https://api.lever.co/v0/postings/{board}/{job_id}")
    return strip_html(data.get("descriptionPlain") or data.get("description", ""))


def _ashby(board: str, job_id: str) -> str:
    # Ashby has no per-job endpoint, so pull the board and pick the row out.
    data = http_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    for job in data.get("jobs", []) or []:
        if str(job.get("id")) == job_id:
            return strip_html(job.get("descriptionHtml") or job.get("descriptionPlain", ""))
    return ""


def fetch_description(posting: Posting) -> str:
    """Return the posting body, or "" if this URL isn't on a known ATS."""
    for pattern, fetch in ((GREENHOUSE, _greenhouse), (LEVER, _lever), (ASHBY, _ashby)):
        m = pattern.search(posting.url or "")
        if m:
            try:
                return fetch(m.group(1), m.group(2))
            except SourceError as exc:
                log.debug("enrich %s: %s", posting.url, exc)
                return ""
    return ""


def enrichable(posting: Posting) -> bool:
    return bool(
        not posting.description
        and any(p.search(posting.url or "") for p in (GREENHOUSE, LEVER, ASHBY))
    )


def enrich(postings: list[Posting], workers: int = 8) -> int:
    """Fill in descriptions in place. Returns how many we managed to get.

    Failures are silent by design: an ATS that rate-limits us shouldn't turn
    into an error the user has to think about, it should just mean that
    posting gets scored on its title like all the others.
    """
    targets = [p for p in postings if enrichable(p)]
    if not targets:
        return 0

    filled = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_description, p): p for p in targets}
        for future in as_completed(futures):
            posting = futures[future]
            try:
                text = future.result()
            except Exception as exc:  # noqa: BLE001
                log.debug("enrich failed for %s: %s", posting.url, exc)
                continue
            if text:
                posting.description = text
                filled += 1
    log.info("enriched %d/%d postings", filled, len(targets))
    return filled
