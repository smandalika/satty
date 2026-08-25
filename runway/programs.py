"""The sophomore-program calendar.

Separate from the feed pipeline on purpose. These entries aren't scraped and
they aren't scored — they're a hand-kept list of the programs that explicitly
want second-years, surfaced by where today falls in their application window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

PROGRAMS_PATH = Path(__file__).parent / "data" / "programs.yml"


@dataclass
class Program:
    company: str
    program: str
    url: str
    eligibility: str
    opens: int
    closes: int
    note: str = ""

    def months_until_open(self, today: date | None = None) -> int:
        """Months until the window opens; 0 once it's open."""
        today = today or date.today()
        if self.is_open(today):
            return 0
        delta = (self.opens - today.month) % 12
        return delta or 12

    def is_open(self, today: date | None = None) -> bool:
        """True if we're inside the window, handling windows that wrap a year."""
        month = (today or date.today()).month
        if self.opens <= self.closes:
            return self.opens <= month <= self.closes
        return month >= self.opens or month <= self.closes  # e.g. Oct -> Jan

    @property
    def window(self) -> str:
        names = "  Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        return f"{names[self.opens - 1]}–{names[self.closes - 1]}"

    def status(self, today: date | None = None) -> str:
        if self.is_open(today):
            return "open now"
        months = self.months_until_open(today)
        return f"opens in ~{months} month{'s' if months != 1 else ''}"


@lru_cache(maxsize=1)
def load_programs(path: str = "") -> list[Program]:
    raw = yaml.safe_load(Path(path or PROGRAMS_PATH).read_text()) or {}
    return [Program(**entry) for entry in raw.get("programs", [])]


def upcoming(today: date | None = None, horizon_months: int = 3) -> list[Program]:
    """Open now first, then whatever opens inside the horizon."""
    today = today or date.today()
    relevant = [
        p for p in load_programs()
        if p.is_open(today) or p.months_until_open(today) <= horizon_months
    ]
    relevant.sort(key=lambda p: (p.months_until_open(today), p.company))
    return relevant


def render_terminal(programs: list[Program], today: date | None = None) -> str:
    if not programs:
        return "No sophomore programs opening in this horizon.\n"
    lines = [
        f"\n{len(programs)} sophomore program{'s' if len(programs) != 1 else ''} to watch\n",
        "These don't appear in any feed. Windows drift year to year — the linked",
        "page is the truth, this list is just the reminder to go look.\n",
    ]
    for p in programs:
        flag = "OPEN" if p.is_open(today) else "    "
        lines.append(f"{flag}  {p.company} — {p.program}")
        lines.append(f"        {p.eligibility} · typically {p.window} · {p.status(today)}")
        if p.note:
            lines.append(f"        {p.note}")
        lines.append(f"        {p.url}")
        lines.append("")
    return "\n".join(lines)
