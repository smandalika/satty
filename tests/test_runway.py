"""Tests for the parts where being wrong is expensive: the filters that
decide what you never see, and the store that decides what you see twice."""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runway.config import Profile
from runway.models import Posting
from runway.programs import Program, upcoming
from runway.scoring import Context, normalize_terms, passes_filters, rank, score
from runway.sources.github_feeds import GithubListingsSource
from runway.store import Store


def make_posting(**kw) -> Posting:
    base = dict(
        company="Acme",
        title="Software Engineer Intern",
        url="https://job-boards.greenhouse.io/acme/jobs/1",
        source="test",
        posted_at=datetime.now(timezone.utc) - timedelta(hours=2),
        locations=["Remote"],
        terms=["Summer 2027"],
        category="Software",
    )
    base.update(kw)
    return Posting(**base)


@pytest.fixture
def profile() -> Profile:
    return Profile(
        name="Test",
        grad_year=2029,
        skills=["python"],
        roles=["software engineer"],
        categories=["Software"],
        locations=["Remote"],
        terms=["Summer 2027", "Fall 2026"],
    )


# --- identity ------------------------------------------------------------

def test_same_job_from_two_feeds_gets_one_key():
    a = make_posting(source="simplify", url="https://x.com/job/1?utm_source=a")
    b = make_posting(source="vansh", url="https://x.com/job/1/")
    assert a.key == b.key


def test_different_jobs_get_different_keys():
    assert make_posting(title="SWE Intern").key != make_posting(title="Data Intern").key


# --- hard filters --------------------------------------------------------

def test_graduate_only_posting_is_dropped(profile):
    p = make_posting(degrees=["Master's", "PhD"])
    ok, why = passes_filters(p, profile)
    assert not ok and "graduate degree" in why


def test_bachelors_posting_survives_and_scores_higher(profile):
    plain = score(make_posting(), profile)
    undergrad = score(make_posting(degrees=["Bachelor's"]), profile)
    assert undergrad.sophomore_fit > plain.sophomore_fit


def test_wrong_term_is_dropped(profile):
    ok, why = passes_filters(make_posting(terms=["Summer 2026"]), profile)
    assert not ok and "term" in why


def test_untagged_term_is_kept(profile):
    """A missing term is missing data, not a mismatch — don't hide it."""
    ok, _ = passes_filters(make_posting(terms=[]), profile)
    assert ok


def test_senior_title_is_dropped(profile):
    ok, why = passes_filters(make_posting(title="Senior Software Engineer"), profile)
    assert not ok and "senior" in why.lower()


def test_phd_language_vetoes(profile):
    ok, _ = passes_filters(make_posting(title="Research Intern - PhD"), profile)
    assert not ok


def test_sponsorship_filter_only_applies_when_needed(profile):
    p = make_posting(sponsorship="Does Not Offer Sponsorship")
    assert passes_filters(p, profile)[0]
    profile.needs_sponsorship = True
    assert not passes_filters(p, profile)[0]


def test_stale_posting_is_dropped(profile):
    old = make_posting(posted_at=datetime.now(timezone.utc) - timedelta(days=90))
    assert not passes_filters(old, profile)[0]


# --- scoring -------------------------------------------------------------

def test_fresher_posting_outranks_identical_older_one(profile):
    fresh = score(make_posting(posted_at=datetime.now(timezone.utc)), profile)
    stale = score(
        make_posting(posted_at=datetime.now(timezone.utc) - timedelta(days=10)), profile
    )
    assert fresh.total > stale.total


def test_named_program_dominates(profile):
    generic = score(make_posting(company="Google", title="Software Engineer Intern"), profile)
    step = score(make_posting(company="Google", title="STEP Intern"), profile)
    # STEP pins the 45-point ceiling; the gap is what matters.
    assert step.sophomore_fit >= 45
    assert step.sophomore_fit > generic.sophomore_fit + 15


def test_high_volume_company_is_penalised(profile):
    posting = make_posting(company="Megacorp")
    ctx = Context(company_volume={"megacorp": 50})
    busy = score(posting, profile, ctx)
    quiet = score(posting, profile, Context(company_volume={"megacorp": 1}))
    assert busy.sophomore_fit < quiet.sophomore_fit


def test_gated_ats_suppresses_the_lone_listing_bonus(profile):
    """A giant on Workday with one scraped role is not a shop that reads
    every application — the two signals must not both fire."""
    posting = make_posting(url="https://x.wd1.myworkdayjobs.com/job/1")
    s = score(posting, profile, Context(company_volume={"acme": 1}))
    reasons = " ".join(s.reasons)
    assert "every application gets read" not in reasons
    assert "enterprise portal" in reasons


def test_description_language_is_used(profile):
    """A description we fetched should move the score, in both directions."""
    neutral = score(make_posting(description="Build things with a great team."), profile)
    leaning = score(make_posting(description="Open for juniors or seniors."), profile)
    open_ = score(make_posting(description="Open to sophomores and all undergraduates."), profile)
    assert open_.sophomore_fit > neutral.sophomore_fit > leaning.sophomore_fit


def test_description_can_veto_outright(profile):
    """'Must be a rising senior' is not a penalty, it's a no."""
    assert score(make_posting(description="Must be a rising senior."), profile) is None


def test_rank_sorts_and_applies_min_score(profile):
    profile.min_score = 200  # nothing can clear this
    assert rank([make_posting()], profile) == []


def test_normalize_terms_parses_variants():
    assert normalize_terms(["Summer 2027"]) == {("summer", 2027)}
    assert normalize_terms(["Fall '26"]) == {("fall", 2026)}
    assert normalize_terms(["N/A"]) == set()


# --- feed parsing --------------------------------------------------------

def test_inactive_rows_are_skipped():
    src = GithubListingsSource("x/y")
    assert src._parse({"active": False, "url": "u", "company_name": "c", "title": "t"}) is None
    assert src._parse({"active": True, "is_visible": False, "url": "u",
                       "company_name": "c", "title": "t"}) is None


def test_season_key_is_read_as_a_term():
    """The two feeds disagree on schema; both must yield a usable term."""
    src = GithubListingsSource("x/y")
    p = src._parse({
        "active": True, "is_visible": True, "url": "https://u/1",
        "company_name": "C", "title": "T", "date_posted": 1787327736, "season": "Winter",
    })
    assert p.terms == ["Winter"]


def test_unparseable_date_is_skipped():
    src = GithubListingsSource("x/y")
    assert src._parse({"active": True, "url": "u", "company_name": "c",
                       "title": "t", "date_posted": "nonsense"}) is None


# --- store ---------------------------------------------------------------

def test_store_reports_each_posting_once(tmp_path, profile):
    store = Store(tmp_path / "t.db")
    scored = [s for s in [score(make_posting(), profile)] if s]
    assert len(store.filter_new(scored)) == 1
    store.record(scored)
    assert store.filter_new(scored) == []
    store.close()


def test_recording_twice_is_harmless(tmp_path, profile):
    store = Store(tmp_path / "t.db")
    scored = [score(make_posting(), profile)]
    store.record(scored)
    store.record(scored)
    assert store.stats()["tracked"] == 1
    store.close()


# --- programs ------------------------------------------------------------

def test_window_that_wraps_the_new_year():
    p = Program("X", "P", "u", "e", opens=10, closes=1)
    assert p.is_open(date(2026, 12, 1))
    assert p.is_open(date(2027, 1, 20))
    assert not p.is_open(date(2026, 6, 1))


def test_normal_window():
    p = Program("X", "P", "u", "e", opens=9, closes=11)
    assert p.is_open(date(2026, 10, 1))
    assert not p.is_open(date(2026, 1, 1))


def test_open_programs_sort_first():
    items = upcoming(date(2026, 9, 15))
    assert items and items[0].is_open(date(2026, 9, 15))
