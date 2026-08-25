"""Rendering: a terminal table for you, an HTML page for everything else."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from .config import Profile
from .models import Scored

TIER_LABEL = {
    "apply-now": ("Apply now", "#0f7b3f"),
    "strong": ("Strong match", "#1f6feb"),
    "worth-a-shot": ("Worth a shot", "#9a6700"),
    "long-shot": ("Long shot", "#6b6b6b"),
}


def _age(scored: Scored) -> str:
    h = scored.posting.age_hours
    if h < 1:
        return "just now"
    if h < 24:
        return f"{int(h)}h ago"
    return f"{int(h / 24)}d ago"


def render_terminal(items: list[Scored], profile: Profile, limit: int = 25) -> str:
    if not items:
        return "No new matches this run.\n"

    lines = [f"\n{len(items)} new match{'es' if len(items) != 1 else ''} for {profile.name or 'you'}\n"]
    for i, s in enumerate(items[:limit], 1):
        p = s.posting
        loc = ", ".join(p.locations[:2]) or "location not listed"
        lines.append(f"{i:>2}. [{s.total:>4.0f}] {p.company} — {p.title}")
        lines.append(
            f"     {TIER_LABEL[s.tier][0]} · {loc} · {_age(s)}"
            f" · soph {s.sophomore_fit:.0f}/45 · fit {s.profile_fit:.0f}/35 · fresh {s.freshness:.0f}/20"
        )
        for reason in s.reasons[:3]:
            lines.append(f"     · {reason}")
        lines.append(f"     {p.url}")
        lines.append("")
    if len(items) > limit:
        lines.append(f"...and {len(items) - limit} more (see the HTML digest).\n")
    return "\n".join(lines)


def render_html(
    items: list[Scored],
    profile: Profile,
    standalone: bool = True,
    programs: list | None = None,
) -> str:
    """Render the digest.

    standalone=True gives a complete file you can open from disk.
    standalone=False gives title+style+body only, for embedding.
    """
    now = datetime.now(timezone.utc).strftime("%b %d, %Y at %H:%M UTC")
    who = html.escape(profile.name or "you")

    cards = []
    for s in items:
        p = s.posting
        label, color = TIER_LABEL[s.tier]
        reasons = "".join(f"<li>{html.escape(r)}</li>" for r in s.reasons[:5])
        locs = html.escape(", ".join(p.locations[:3]) or "Location not listed")
        terms = html.escape(", ".join(p.terms) or "Term not stated")
        cards.append(f"""
        <article class="card">
          <div class="card-top">
            <div>
              <h3><a href="{html.escape(p.url)}" target="_blank" rel="noopener">{html.escape(p.title)}</a></h3>
              <p class="company">{html.escape(p.company)}</p>
            </div>
            <div class="score" style="--tier:{color}">
              <span class="num">{s.total:.0f}</span>
              <span class="tier">{label}</span>
            </div>
          </div>
          <p class="meta">{locs} &middot; {terms} &middot; posted {_age(s)}</p>
          <div class="bars">
            <div class="bar"><span>Sophomore fit</span><i style="--w:{s.sophomore_fit / 45 * 100:.0f}%"></i><b>{s.sophomore_fit:.0f}/45</b></div>
            <div class="bar"><span>Profile fit</span><i style="--w:{s.profile_fit / 35 * 100:.0f}%"></i><b>{s.profile_fit:.0f}/35</b></div>
            <div class="bar"><span>Freshness</span><i style="--w:{s.freshness / 20 * 100:.0f}%"></i><b>{s.freshness:.0f}/20</b></div>
          </div>
          <ul class="why">{reasons}</ul>
        </article>""")

    prog_html = ""
    if programs:
        rows = "".join(
            f'<li class="{"open" if p.is_open() else ""}">'
            f'<a href="{html.escape(p.url)}" target="_blank" rel="noopener">'
            f"{html.escape(p.company)} &mdash; {html.escape(p.program)}</a>"
            f'<span>{html.escape(p.eligibility)} &middot; {html.escape(p.status())}</span></li>'
            for p in programs
        )
        prog_html = f"""
<section class="programs">
  <h2>Built for sophomores</h2>
  <p class="note">These never appear in the scraped feeds — they run on their own
  calendar. Windows drift each year, so the linked page is the truth.</p>
  <ul>{rows}</ul>
</section>"""

    empty = '<p class="empty">Nothing new this run. That is the normal result most hours — the point is that you find out within one when there is.</p>'
    body = f"""
<header>
  <p class="kicker">Runway &middot; beta</p>
  <h1>{len(items)} new internship{'s' if len(items) != 1 else ''} for {who}</h1>
  <p class="sub">Scored for a {html.escape(profile.year)} &middot; generated {now}</p>
</header>
<main>{''.join(cards) if items else empty}{prog_html}</main>
<footer>
  <p>Score = sophomore fit (45) + profile fit (35) + freshness (20). Freshness halves every three days,
  so a listing that sat for a week can never outrank one posted this morning.</p>
</footer>"""

    style = """
:root {
  --bg:#fbfbfa; --panel:#fff; --ink:#1a1a19; --muted:#6b6b68;
  --line:#e5e4e1; --accent:#1f6feb; --track:#eeedea;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#141413; --panel:#1c1c1a; --ink:#f0efec; --muted:#9a9a95;
    --line:#2c2c29; --accent:#6ea8fe; --track:#2c2c29;
  }
}
:root[data-theme="dark"] {
  --bg:#141413; --panel:#1c1c1a; --ink:#f0efec; --muted:#9a9a95;
  --line:#2c2c29; --accent:#6ea8fe; --track:#2c2c29;
}
* { box-sizing:border-box; }
body {
  margin:0; padding:2.5rem 1.25rem 4rem; background:var(--bg); color:var(--ink);
  font:16px/1.55 ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
header, main, footer { max-width:760px; margin:0 auto; }
.kicker { margin:0; font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }
h1 { margin:.35rem 0 .3rem; font-size:1.9rem; line-height:1.15; letter-spacing:-.02em; }
.sub { margin:0 0 2rem; color:var(--muted); font-size:.9rem; }
.card {
  background:var(--panel); border:1px solid var(--line); border-radius:12px;
  padding:1.1rem 1.2rem; margin-bottom:.9rem;
}
.card-top { display:flex; gap:1rem; justify-content:space-between; align-items:flex-start; }
.card h3 { margin:0 0 .2rem; font-size:1.05rem; line-height:1.3; }
.card h3 a { color:var(--ink); text-decoration:none; }
.card h3 a:hover { color:var(--accent); text-decoration:underline; }
.company { margin:0; color:var(--muted); font-size:.9rem; }
.score { text-align:right; flex:0 0 auto; }
.score .num { display:block; font-size:1.5rem; font-weight:650; color:var(--tier); letter-spacing:-.02em; }
.score .tier { font-size:.7rem; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }
.meta { margin:.65rem 0 .8rem; font-size:.82rem; color:var(--muted); }
.bars { display:grid; gap:.3rem; margin-bottom:.75rem; }
.bar { display:grid; grid-template-columns:7.5rem 1fr 3.2rem; align-items:center; gap:.6rem; font-size:.75rem; color:var(--muted); }
.bar i { height:5px; border-radius:99px; background:var(--track); display:block; position:relative; }
.bar i::after { content:""; position:absolute; inset:0 auto 0 0; width:var(--w); border-radius:99px; background:var(--accent); }
.bar b { font-weight:500; text-align:right; font-variant-numeric:tabular-nums; }
.why { margin:0; padding-left:1.1rem; font-size:.82rem; color:var(--muted); }
.why li { margin:.15rem 0; }
.empty { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:1.5rem; color:var(--muted); }
.programs { margin-top:2.5rem; }
.programs h2 { font-size:1.1rem; margin:0 0 .3rem; letter-spacing:-.01em; }
.programs .note { margin:0 0 .9rem; color:var(--muted); font-size:.82rem; }
.programs ul { list-style:none; margin:0; padding:0; }
.programs li {
  display:flex; flex-wrap:wrap; gap:.2rem 1rem; justify-content:space-between;
  align-items:baseline; padding:.6rem .8rem; border:1px solid var(--line);
  border-radius:9px; margin-bottom:.4rem; background:var(--panel);
}
.programs li.open { border-color:#0f7b3f66; }
.programs li.open a::before { content:"OPEN "; color:#0f7b3f; font-size:.68rem; letter-spacing:.08em; }
.programs a { color:var(--ink); text-decoration:none; font-size:.9rem; font-weight:500; }
.programs a:hover { color:var(--accent); text-decoration:underline; }
.programs span { color:var(--muted); font-size:.76rem; }
footer { margin-top:2rem; padding-top:1.2rem; border-top:1px solid var(--line); color:var(--muted); font-size:.78rem; }
@media (max-width:520px) {
  .card-top { flex-direction:column; } .score { text-align:left; }
  .bar { grid-template-columns:6.5rem 1fr 3rem; }
}"""

    head = f"<title>Runway Digest</title>\n<style>{style}</style>"
    if not standalone:
        return head + body
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{head}
</head><body>{body}</body></html>"""
