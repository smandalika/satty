"""Command line entry point.

    python -m runway run          fetch, score, report only what's new
    python -m runway run --all    ignore the seen-store, show everything
    python -m runway preview      score without recording (safe to re-run)
    python -m runway explain URL  why did this posting score what it scored
    python -m runway stats        what the store knows
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

from .config import Profile, default_profile_path
from .digest import render_html, render_terminal
from .enrich import enrich, enrichable
from .models import Posting
from .notify import notify
from . import programs as programs_mod
from .scoring import passes_filters, rank, score
from .sources import build_sources
from .store import Store


def _collect(profile_dir: Path) -> list[Posting]:
    """Fetch every source, then de-duplicate across them.

    The same job appears in several feeds; keeping the copy with the earliest
    posted_at and any description text gives the best row.
    """
    cfg = {}
    sources_file = profile_dir / "sources.yml"
    if sources_file.exists():
        cfg = yaml.safe_load(sources_file.read_text()) or {}

    merged: dict[str, Posting] = {}
    for src in build_sources(cfg):
        for posting in src.safe_fetch():
            existing = merged.get(posting.key)
            if existing is None:
                merged[posting.key] = posting
                continue
            if not existing.description and posting.description:
                existing.description = posting.description
            if posting.posted_at < existing.posted_at:
                existing.posted_at = posting.posted_at
            for field in ("terms", "locations", "degrees"):
                if not getattr(existing, field) and getattr(posting, field):
                    setattr(existing, field, getattr(posting, field))
    return list(merged.values())


def cmd_run(args) -> int:
    profile = Profile.load(args.profile)
    profile_dir = Path(args.profile).resolve().parent

    postings = _collect(profile_dir)
    if not postings:
        print("No sources returned anything. Check your network and try again.", file=sys.stderr)
        return 2

    ranked = rank(postings, profile)

    # Two passes. The first is title-only and cheap; it tells us which few
    # dozen postings are worth spending HTTP requests on. Then we fetch those
    # descriptions and score again, this time reading what the posting
    # actually says about who may apply.
    if not args.no_enrich:
        shortlist = [s.posting for s in ranked[: args.enrich_top] if enrichable(s.posting)]
        if shortlist:
            got = enrich(shortlist)
            if got:
                print(f"Read {got} full job descriptions.", file=sys.stderr)
                ranked = rank(postings, profile)

    print(f"Fetched {len(postings)} postings; {len(ranked)} clear your bar.", file=sys.stderr)

    store = Store(args.db)
    try:
        items = ranked if args.all else store.filter_new(ranked)
        if args.limit:
            items = items[: args.limit]

        print(render_terminal(items, profile))

        open_now = [p for p in programs_mod.upcoming(horizon_months=1) if p.is_open()]
        if open_now:
            names = ", ".join(f"{p.company} {p.program.split(' /')[0]}" for p in open_now[:4])
            print(
                f"Also open right now (not in any feed): {names}"
                f"{' and more' if len(open_now) > 4 else ''}."
                "\nRun `python -m runway programs` for the full list.\n",
                file=sys.stderr,
            )

        if args.html:
            Path(args.html).write_text(
                render_html(items, profile, programs=programs_mod.upcoming())
            )
            print(f"HTML digest -> {args.html}", file=sys.stderr)
        if args.json:
            Path(args.json).write_text(
                json.dumps([s.to_dict() for s in items], indent=2)
            )
            print(f"JSON -> {args.json}", file=sys.stderr)

        sent = []
        if items and not args.no_notify:
            sent = notify(items, profile)
            if sent:
                print(f"Notified via {', '.join(sent)}.", file=sys.stderr)

        if not args.dry_run:
            # Record everything ranked, not just what we showed, so a --limit
            # run doesn't cause the rest to re-alert tomorrow.
            store.record(ranked, notified=bool(sent))
    finally:
        store.close()
    return 0


def cmd_preview(args) -> int:
    args.all = True
    args.dry_run = True
    args.no_notify = True
    return cmd_run(args)


def cmd_explain(args) -> int:
    profile = Profile.load(args.profile)
    postings = _collect(Path(args.profile).resolve().parent)
    needle = args.query.lower()
    hits = [
        p for p in postings
        if needle in p.url.lower()
        or needle in f"{p.company} {p.title}".lower()
    ]
    if not hits:
        print(f"Nothing matching {args.query!r} in the current feeds.")
        return 1

    for p in hits[:5]:
        print(f"\n{p.company} — {p.title}\n{p.url}")
        ok, why = passes_filters(p, profile)
        if not ok:
            print(f"  FILTERED OUT: {why}")
            continue
        s = score(p, profile)
        print(f"  total {s.total:.0f}  ({s.tier})")
        print(f"    sophomore fit {s.sophomore_fit:.0f}/45")
        print(f"    profile fit   {s.profile_fit:.0f}/35")
        print(f"    freshness     {s.freshness:.0f}/20")
        for r in s.reasons:
            print(f"    · {r}")
        if s.total < profile.min_score:
            print(f"  below your min_score of {profile.min_score:.0f}, so it would be hidden")
    return 0


def cmd_programs(args) -> int:
    items = programs_mod.upcoming(horizon_months=args.horizon)
    print(programs_mod.render_terminal(items))
    return 0


def cmd_stats(args) -> int:
    store = Store(args.db)
    try:
        st = store.stats()
        print(f"tracked postings : {st['tracked']}")
        print(f"marked applied   : {st['applied']}")
        print(f"last run         : {st['last_run'] or 'never'}")
    finally:
        store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="runway", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default=str(default_profile_path()))
    ap.add_argument("--db", default="runway.db")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="fetch, score and report new matches")
    run.add_argument("--all", action="store_true", help="include postings already seen")
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--html", metavar="PATH", help="write an HTML digest")
    run.add_argument("--json", metavar="PATH", help="write raw JSON")
    run.add_argument("--no-notify", action="store_true")
    run.add_argument("--dry-run", action="store_true", help="don't record what was seen")
    run.add_argument("--no-enrich", action="store_true", help="skip fetching job descriptions")
    run.add_argument("--enrich-top", type=int, default=60, metavar="N",
                     help="how many shortlisted postings to fetch descriptions for")
    run.set_defaults(func=cmd_run)

    prev = sub.add_parser("preview", help="score everything without recording or notifying")
    prev.add_argument("--limit", type=int, default=25)
    prev.add_argument("--html", metavar="PATH")
    prev.add_argument("--json", metavar="PATH")
    prev.add_argument("--no-enrich", action="store_true")
    prev.add_argument("--enrich-top", type=int, default=60, metavar="N")
    prev.set_defaults(func=cmd_preview)

    exp = sub.add_parser("explain", help="show the score breakdown for one posting")
    exp.add_argument("query", help="a URL, company or title fragment")
    exp.set_defaults(func=cmd_explain)

    pg = sub.add_parser("programs", help="sophomore-only programs opening soon")
    pg.add_argument("--horizon", type=int, default=3, metavar="MONTHS")
    pg.set_defaults(func=cmd_programs)

    st = sub.add_parser("stats", help="what the store has tracked")
    st.set_defaults(func=cmd_stats)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
