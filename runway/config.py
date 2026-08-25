"""Profile loading. The profile is the whole configuration surface."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# A sophomore's realistic targets: the summer after their junior year starts is
# too far out, and the current summer's cycle has already closed.
DEFAULT_TERMS = ["Summer 2027", "Fall 2026", "Winter 2027", "Spring 2027"]


@dataclass
class Profile:
    name: str = ""
    year: str = "sophomore"
    grad_year: int = 0
    school: str = ""
    majors: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_ok: bool = True
    needs_sponsorship: bool = False
    us_work_authorized: bool = True
    terms: list[str] = field(default_factory=lambda: list(DEFAULT_TERMS))
    exclude_companies: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    min_score: float = 32.0
    max_age_days: int = 21

    @property
    def keywords(self) -> list[str]:
        """Everything we keyword-match a posting against."""
        return [k.lower() for k in (self.skills + self.roles + self.majors) if k]

    @classmethod
    def load(cls, path: str | Path) -> "Profile":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"No profile at {path}. Copy profile.example.yml to profile.yml and edit it."
            )
        raw = yaml.safe_load(path.read_text()) or {}
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"Unknown profile keys: {', '.join(sorted(unknown))}")
        profile = cls(**raw)
        profile.validate()
        return profile

    def validate(self) -> None:
        if not self.keywords:
            raise ValueError("Profile needs at least one of: skills, roles, majors.")
        if self.grad_year and not (2020 <= self.grad_year <= 2040):
            raise ValueError(f"grad_year {self.grad_year} looks wrong.")


def default_profile_path() -> Path:
    return Path(os.environ.get("RUNWAY_PROFILE", "profile.yml"))
