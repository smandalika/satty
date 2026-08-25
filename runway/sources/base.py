from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from ..models import Posting

log = logging.getLogger("runway.sources")

USER_AGENT = "runway-beta/0.1 (personal internship tracker)"
TIMEOUT = 30


class SourceError(RuntimeError):
    """A source could not be read. Never fatal — we skip it and carry on."""


def http_json(url: str, retries: int = 3) -> Any:
    """GET JSON with backoff. Raises SourceError rather than bubbling urllib."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(2**attempt)
    raise SourceError(f"{url}: {last}") from last


class Source:
    """Base class. Subclasses implement fetch() and set a readable name."""

    name = "source"

    def fetch(self) -> list[Posting]:  # pragma: no cover - interface
        raise NotImplementedError

    def safe_fetch(self) -> list[Posting]:
        """Never let one broken feed take down the run."""
        try:
            postings = self.fetch()
            log.info("%s: %d postings", self.name, len(postings))
            return postings
        except SourceError as exc:
            log.warning("%s unavailable: %s", self.name, exc)
            return []
        except Exception as exc:  # noqa: BLE001 - a source must never crash a run
            log.warning("%s failed unexpectedly: %s", self.name, exc)
            return []
