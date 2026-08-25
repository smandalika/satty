"""Scoring: is this worth a sophomore's evening?

Three components, deliberately kept separate so a listing can explain itself:

  sophomore_fit (0-45)  will they even read an application from a 2nd-year?
  profile_fit   (0-35)  does it match what you can actually do?
  freshness     (0-20)  did it go up recently enough that you're early?

Hard filters run first. A posting that fails one is dropped, not scored — the
point of this tool is a short list you'll actually work through.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .config import Profile
from .models import Posting, Scored

SIGNALS_PATH = Path(__file__).parent / "data" / "signals.yml"

TERM_RE = re.compile(r"(spring|summer|fall|autumn|winter)\s*'?(\d{2,4})", re.I)
SEASON_ORDER = {"spring": 0, "summer": 1, "fall": 2, "autumn": 2, "winter": 3}

UNDERGRAD_DEGREES = {"bachelor's", "bachelors", "associate's", "associates"}


@dataclass
class Context:
    """Corpus-derived facts a single posting can't tell you on its own."""

    company_volume: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, postings: list[Posting]) -> "Context":
        vol: dict[str, int] = {}
        for p in postings:
            vol[p.company.lower()] = vol.get(p.company.lower(), 0) + 1
        return cls(company_volume=vol)

    def volume(self, posting: Posting) -> int:
        return self.company_volume.get(posting.company.lower(), 1)


@lru_cache(maxsize=1)
def load_signals(path: str = "") -> dict:
    return yaml.safe_load(Path(path or SIGNALS_PATH).read_text()) or {}


def _any(patterns, text: str) -> str | None:
    """Return the first pattern that matches, so we can cite it as a reason."""
    for pat in patterns or []:
        if re.search(pat, text, re.I):
            return pat
    return None


def _clean(pat: str) -> str:
    """Turn a regex back into something readable for the reasons list."""
    return re.sub(r"\\b|\\\.|\\?|\(|\)|\?", "", pat).replace("|", " / ").strip()


# --------------------------------------------------------------------------
# Hard filters
# --------------------------------------------------------------------------

def normalize_terms(terms: list[str]) -> set[tuple[str, int]]:
    out = set()
    for t in terms:
        for season, year in TERM_RE.findall(t or ""):
            y = int(year)
            out.add((season.lower(), 2000 + y if y < 100 else y))
    return out


def term_is_eligible(posting: Posting, profile: Profile) -> tuple[bool, str]:
    """Drop terms you can't take, and terms that have already started.

    A sophomore in autumn 2026 is recruiting for summer 2027. A `Summer 2026`
    posting still sitting in a feed is a stale row, not an opportunity.
    """
    wanted = normalize_terms(profile.terms)
    got = normalize_terms(posting.terms)
    if not got:
        return True, ""  # untagged: let the scorer decide rather than dropping it
    if not wanted:
        return True, ""
    if got & wanted:
        return True, ""
    return False, f"term {'/'.join(sorted(t for t in posting.terms))} not in your list"


def passes_filters(posting: Posting, profile: Profile) -> tuple[bool, str]:
    signals = load_signals()
    hay = posting.haystack
    title = posting.title.lower()

    for company in profile.exclude_companies:
        if company and company.lower() in posting.company.lower():
            return False, f"excluded company ({company})"

    hit = _any([re.escape(k.lower()) for k in profile.exclude_keywords], hay)
    if hit:
        return False, f"excluded keyword ({_clean(hit)})"

    hit = _any(signals.get("not_an_internship"), title)
    if hit:
        return False, f"title reads as a senior role ({_clean(hit)})"

    if profile.needs_sponsorship and posting.sponsorship in {
        "Does Not Offer Sponsorship",
        "U.S. Citizenship is Required",
    }:
        return False, "no visa sponsorship"

    if not profile.us_work_authorized and "U.S. Citizenship" in posting.sponsorship:
        return False, "requires US citizenship"

    # The feeds tag which degrees a posting accepts. A list that names only
    # graduate degrees is the clearest "not for you" the data ever gives us.
    if posting.degrees:
        degrees = {d.strip().lower() for d in posting.degrees}
        if not (degrees & UNDERGRAD_DEGREES):
            return False, f"graduate degree required ({', '.join(sorted(posting.degrees))})"

    hit = _any(signals.get("closed_phrases", {}).get("hard"), hay)
    if hit:
        return False, f"explicitly closed to you ({_clean(hit)})"

    ok, why = term_is_eligible(posting, profile)
    if not ok:
        return False, why

    # Checked last on purpose: "you aren't eligible" is a more useful answer
    # than "this is old", so when both are true we want to report the former.
    if posting.age_hours > profile.max_age_days * 24:
        return False, f"posted {int(posting.age_hours / 24)}d ago, past your max_age_days"

    return True, ""


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------

def score_sophomore_fit(
    posting: Posting, profile: Profile, ctx: Context | None = None
) -> tuple[float, list[str]]:
    """0-45. The differentiator: who will actually reply to a second-year?

    Most postings never state a class year, so this leans on proxies for how a
    company screens rather than waiting for language that usually isn't there.
    """
    signals = load_signals()
    ctx = ctx or Context()
    reasons: list[str] = []
    score = 10.0  # neutral prior
    title = posting.title.lower()
    company = posting.company.lower()
    hay = posting.haystack

    for prog in signals.get("sophomore_programs", []):
        if re.search(prog["company"], company, re.I) and re.search(prog["pattern"], title, re.I):
            reasons.append(f"named underclassman program at {posting.company}")
            score += 30
            break

    hit = _any(signals.get("open_phrases", {}).get("strong"), hay)
    if hit:
        reasons.append(f"posting says '{_clean(hit)}'")
        score += 14
    else:
        hit = _any(signals.get("open_phrases", {}).get("mild"), hay)
        if hit:
            reasons.append(f"open-sounding language ('{_clean(hit)}')")
            score += 4

    hit = _any(signals.get("closed_phrases", {}).get("soft"), hay)
    if hit:
        reasons.append(f"leans upperclassman ('{_clean(hit)}')")
        score -= 12

    # Explicitly undergrad-only postings are the ones written with you in mind.
    if posting.degrees:
        degrees = {d.strip().lower() for d in posting.degrees}
        if degrees <= UNDERGRAD_DEGREES:
            reasons.append("undergraduate only — not competing with grad students")
            score += 12
        elif "phd" in degrees or "master's" in degrees:
            reasons.append("also open to master's/PhD applicants")
            score -= 6

    # Two proxies for how a company screens, resolved together because they
    # can disagree: a big consultancy with one scraped listing is not a shop
    # that reads every application, and saying so would be worse than useless.
    ats = signals.get("ats_signals", {})
    gated = bool(_any([re.escape(d) for d in ats.get("gated", [])], posting.url))
    responsive = bool(_any([re.escape(d) for d in ats.get("responsive", [])], posting.url))

    if gated:
        reasons.append("enterprise portal — usually auto-screened on grad year")
        score -= 5
    elif responsive:
        reasons.append("direct ATS apply — a person reads these")
        score += 6

    volume = ctx.volume(posting)
    if volume >= 20:
        # Volume is trustworthy in this direction: nobody accidentally posts
        # eighty roles. It means a funnel, whatever the ATS looks like.
        reasons.append(f"high-volume funnel ({volume} listings) — screened on grad year")
        score -= 7
    elif not gated:
        # In the other direction it only means something when the company
        # isn't hiding behind an enterprise portal.
        if volume == 1:
            reasons.append("company's only listing — every application gets read")
            score += 9
        elif volume <= 4:
            reasons.append(f"small hiring round ({volume} listings)")
            score += 5

    if posting.description:
        reasons.append("scored against the full job description")
        score += 2

    return max(0.0, min(45.0, score)), reasons


def score_profile_fit(posting: Posting, profile: Profile) -> tuple[float, list[str]]:
    """0-35. Does this match your skills, field and geography?"""
    reasons: list[str] = []
    score = 0.0
    hay = posting.haystack

    matched = [k for k in profile.keywords if re.search(rf"\b{re.escape(k)}\b", hay)]
    if matched:
        # Diminishing returns: five keyword hits isn't five times one.
        score += min(18.0, 7.0 * math.log2(1 + len(matched)))
        reasons.append("matches " + ", ".join(sorted(set(matched))[:4]))

    if profile.categories:
        if posting.category and any(
            c.lower() in posting.category.lower() for c in profile.categories
        ):
            score += 8
            reasons.append(f"in your field ({posting.category})")
        elif posting.category:
            score -= 4

    if profile.locations:
        locs = " | ".join(posting.locations).lower()
        hit = next((l for l in profile.locations if l.lower() in locs), None)
        if hit:
            score += 9
            reasons.append(f"located in {hit}")
        elif profile.remote_ok and "remote" in locs:
            score += 7
            reasons.append("remote")
        elif locs:
            score -= 3

    return max(0.0, min(35.0, score)), reasons


def score_freshness(posting: Posting) -> tuple[float, list[str]]:
    """0-20. Being early is most of the edge a tool like this can give you.

    Halves every three days: applications submitted in a posting's first day
    land in the first screening batch, which is a different queue than week two.
    """
    hours = posting.age_hours
    score = 20.0 * math.pow(0.5, hours / 72.0)
    if hours <= 24:
        return score, [f"posted {int(hours)}h ago — you'd be in the first batch"]
    if hours <= 72:
        return score, [f"posted {int(hours / 24)}d ago"]
    return score, [f"posted {int(hours / 24)}d ago — the queue has built up"]


def score(posting: Posting, profile: Profile, ctx: Context | None = None) -> Scored | None:
    """Score one posting, or return None if a hard filter rejects it."""
    if not passes_filters(posting, profile)[0]:
        return None

    soph, r1 = score_sophomore_fit(posting, profile, ctx)
    prof, r2 = score_profile_fit(posting, profile)
    fresh, r3 = score_freshness(posting)

    return Scored(
        posting=posting,
        total=soph + prof + fresh,
        sophomore_fit=soph,
        profile_fit=prof,
        freshness=fresh,
        reasons=r1 + r2 + r3,
        blockers=[],
    )


def rank(postings: list[Posting], profile: Profile) -> list[Scored]:
    """Score, drop rejects and anything under min_score, best first."""
    ctx = Context.build(postings)
    scored = [s for s in (score(p, profile, ctx) for p in postings) if s is not None]
    scored = [s for s in scored if s.total >= profile.min_score]
    scored.sort(key=lambda s: (-s.total, s.posting.age_hours))
    return scored
