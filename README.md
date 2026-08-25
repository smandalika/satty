# Runway (beta)

An internship tracker for someone who is a **sophomore** — which is the hard
part. Most listings are written for rising seniors, and the ones that aren't
rarely say so out loud. Runway pulls new postings within minutes of them going
up, throws out the ones that will never reply to a second-year, and ranks what
is left by how much of a real shot you have.

```
python -m runway run --html digest.html
```

```
 1. [  64] Kodiak Robotics — Planning Intern - Mission Planning
     Strong match · Mountain View, CA · 4h ago · soph 33/45 · fit 12/35 · fresh 19/20
     · undergraduate only — not competing with grad students
     · direct ATS apply — a person reads these
     · small hiring round (2 listings)
     https://job-boards.greenhouse.io/kodiak/jobs/4378548009
```

## Setup

```bash
pip install -r requirements.txt
cp profile.example.yml profile.yml   # then edit it — this is the whole config
python -m runway preview             # score everything, change nothing
```

`preview` is safe to run as often as you like. `run` is the real thing: it
reports only what it has never shown you before, and remembers what it sent.

## What it actually does

**Finds postings fast.** Two community feeds that thousands of people push new
listings into, refreshed constantly. In testing the newest posting was
one hour old.

**Drops what can't work.** Before anything is scored: graduate-only degree
requirements, terms you can't take, seasons that already started, PhD and
new-grad roles, senior titles, sponsorship mismatches. Roughly 2,300 postings
become a few hundred.

**Reads the real posting.** Titles never say who may apply. About a quarter of
listings sit on Greenhouse, Lever or Ashby, which publish the full description
for free — so Runway shortlists on titles first, then fetches the descriptions
for just those and scores again, this time reading the sentence that actually
matters ("open to all undergraduates" / "must be graduating in 2027").

**Scores what's left, out of 100:**

| Component | Max | What it's asking |
|---|---|---|
| Sophomore fit | 45 | Will they reply to a second-year? |
| Profile fit | 35 | Does it match what you can do and where you'll be? |
| Freshness | 20 | Are you early enough to matter? |

Freshness halves every three days, so a listing that has sat for a week can
never outrank one posted this morning. Being first is most of the edge a tool
like this can give you.

Every result shows its reasoning. If you disagree with a score, `explain` will
tell you exactly which signal produced it:

```bash
python -m runway explain kodiak
```

## Sophomore fit, specifically

This is the part that isn't just a job board. Signals, in rough order of weight:

- **Named underclassman programs** — Google STEP, Microsoft Explore, Jane
  Street INSIGHT and friends. Kept in `runway/data/signals.yml`.
- **Degree requirements** — the feeds tag which degrees a posting accepts.
  Undergraduate-only means you aren't competing with master's students.
- **How the company screens** — a shop with one open role reads every
  application; a firm with eighty runs a funnel that filters on graduation
  date before a human sees you. Company posting volume is a decent proxy, and
  the applicant-tracking system is another: Greenhouse and Lever mean a person
  reads it, an enterprise Workday portal usually means a resume screen. These
  two are resolved together, because a consultancy with one scraped listing is
  not a small shop.
- **Eligibility language** — from the description when we could fetch it.

None of this is magic. It's a prior, and it's transparent, and you can edit
every rule in a YAML file.

## Programs built for sophomores

```bash
python -m runway programs
```

The programs genuinely aimed at second-years — STEP, Explore, Meta University,
Discover Citadel, Sophomore Edge — **never appear in scraped feeds.** They run
on their own calendar, usually opening months before normal internship season.
Missing them is the most expensive mistake a sophomore can make, so Runway
keeps a hand-maintained list in `runway/data/programs.yml` and tells you what
is open now and what opens soon.

Application windows drift year to year. The linked page is always the truth;
this list is the reminder to go look.

## Getting told without checking

Set either and matches come to you:

```bash
export RUNWAY_WEBHOOK_URL=...     # Slack or Discord incoming webhook
export RUNWAY_EMAIL_TO=you@example.com
export RUNWAY_SMTP_HOST=smtp.gmail.com
export RUNWAY_SMTP_USER=... RUNWAY_SMTP_PASS=...   # an app password
```

Then run it on a schedule. Locally:

```
0 * * * * cd /path/to/repo && python -m runway run >> runway.log 2>&1
```

Or fork the repo and let `.github/workflows/runway.yml` do it hourly — add the
same names as repository secrets and it works with no server of your own.

## Commands

| | |
|---|---|
| `run` | Fetch, score, report what's new, remember it |
| `preview` | Score everything, record nothing, notify nobody |
| `programs` | Sophomore-only programs open now or opening soon |
| `explain <query>` | Score breakdown for one posting |
| `stats` | What the store has tracked |

Useful flags: `--all` (ignore what's been seen), `--html PATH`, `--json PATH`,
`--no-enrich` (skip description fetching), `--dry-run`, `--limit N`.

## Adding companies you care about

Copy `sources.example.yml` to `sources.yml` and list Greenhouse, Lever or Ashby
board slugs. Those get watched directly and always come with full descriptions,
so they're scored on what the posting says rather than on its title.

## Honest limits

- **US-centric.** Both feeds are.
- **Windows in `programs.yml` are approximate** and will go stale. They're a
  prompt to check the page, not a source of truth.
- **Sophomore fit is inference, not fact.** When a posting doesn't state a year
  — most don't — the score is a prior built from proxies. It's transparent and
  editable, but it will be wrong sometimes. A high score means "worth your
  evening", not "you'll get it".
- **Enrichment covers about a quarter of postings.** The rest are on portals
  with no public API, and get scored on their titles.
- **It doesn't apply for you,** and shouldn't.

## Tests

```bash
pip install -r requirements-dev.txt && python -m pytest tests/ -q
```

## Layout

```
runway/
  cli.py          commands
  scoring.py      filters and the three score components
  enrich.py       second pass — fetch real job descriptions
  programs.py     the sophomore-program calendar
  store.py        SQLite; what stops repeat alerts
  digest.py       terminal and HTML output
  notify.py       webhook and email
  sources/        one adapter per feed
  data/
    signals.yml   every scoring rule, editable
    programs.yml  the sophomore-program list, editable
```
