"""Seen-posting store.

The whole premise is "tell me the moment it appears", which only works if the
tool remembers what it already told you. SQLite keeps that durable across runs
and machines without a service to babysit.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .models import Scored

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    key         TEXT PRIMARY KEY,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    score       REAL NOT NULL,
    tier        TEXT NOT NULL,
    posted_at   TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    notified    INTEGER NOT NULL DEFAULT 0,
    applied     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS seen_first_seen ON seen(first_seen);
"""


class Store:
    def __init__(self, path: str | Path = "runway.db"):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        with closing(self.conn.cursor()) as cur:
            cur.executescript(SCHEMA)
        self.conn.commit()

    def filter_new(self, scored: list[Scored]) -> list[Scored]:
        """Return only postings this store has never recorded."""
        if not scored:
            return []
        keys = [s.posting.key for s in scored]
        placeholders = ",".join("?" * len(keys))
        rows = self.conn.execute(
            f"SELECT key FROM seen WHERE key IN ({placeholders})", keys
        ).fetchall()
        known = {r["key"] for r in rows}
        return [s for s in scored if s.posting.key not in known]

    def record(self, scored: list[Scored], notified: bool = False) -> int:
        """Mark postings as seen. Idempotent — re-recording is a no-op."""
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                s.posting.key,
                s.posting.company,
                s.posting.title,
                s.posting.url,
                s.total,
                s.tier,
                s.posting.posted_at.isoformat(),
                now,
                1 if notified else 0,
            )
            for s in scored
        ]
        with self.conn:
            cur = self.conn.executemany(
                "INSERT OR IGNORE INTO seen "
                "(key, company, title, url, score, tier, posted_at, first_seen, notified) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                rows,
            )
        return cur.rowcount

    def mark_applied(self, key: str) -> bool:
        with self.conn:
            cur = self.conn.execute("UPDATE seen SET applied=1 WHERE key=?", (key,))
        return cur.rowcount > 0

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*) n, SUM(applied) applied, MAX(first_seen) last FROM seen"
        ).fetchone()
        return {"tracked": row["n"] or 0, "applied": row["applied"] or 0, "last_run": row["last"]}

    def close(self) -> None:
        self.conn.close()
