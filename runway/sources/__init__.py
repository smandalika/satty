"""Feed adapters. Each returns a list of normalized Postings."""
from .base import Source, SourceError, http_json
from .github_feeds import GithubListingsSource, GITHUB_FEEDS
from .greenhouse import GreenhouseSource
from .lever import LeverSource
from .ashby import AshbySource

__all__ = [
    "Source",
    "SourceError",
    "http_json",
    "GithubListingsSource",
    "GITHUB_FEEDS",
    "GreenhouseSource",
    "LeverSource",
    "AshbySource",
    "build_sources",
]


def build_sources(config: dict | None = None) -> list[Source]:
    """Assemble the source list from the `sources:` block of the profile dir.

    The GitHub aggregate feeds are the backbone — they cover thousands of
    companies and update within minutes of a posting going live. The ATS
    adapters exist for companies you specifically care about, where you want
    the full job description (and therefore real eligibility detection)
    rather than just a title.
    """
    config = config or {}
    sources: list[Source] = []
    for feed in config.get("github_feeds", GITHUB_FEEDS):
        sources.append(GithubListingsSource(**feed) if isinstance(feed, dict) else GithubListingsSource(feed))
    for board in config.get("greenhouse", []):
        sources.append(GreenhouseSource(board))
    for board in config.get("lever", []):
        sources.append(LeverSource(board))
    for board in config.get("ashby", []):
        sources.append(AshbySource(board))
    return sources
