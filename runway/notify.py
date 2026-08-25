"""Delivery. A match you don't hear about is the same as no match.

Both channels are opt-in via environment variables so nothing secret ever
lands in the profile file or the repo.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.request
from email.message import EmailMessage

from .config import Profile
from .digest import render_html, render_terminal
from .models import Scored

log = logging.getLogger("runway.notify")


def _webhook_payload(items: list[Scored]) -> dict:
    """Slack and Discord both accept a bare {"text": ...} / {"content": ...}."""
    lines = [f"*{len(items)} new internship match{'es' if len(items) != 1 else ''}*", ""]
    for s in items[:10]:
        p = s.posting
        lines.append(f"`{s.total:>3.0f}` *{p.company}* — {p.title}")
        lines.append(f"      {s.reasons[0] if s.reasons else ''}")
        lines.append(f"      {p.url}")
    if len(items) > 10:
        lines.append(f"_...and {len(items) - 10} more._")
    text = "\n".join(lines)
    return {"text": text, "content": text}


def send_webhook(items: list[Scored], url: str = "") -> bool:
    url = url or os.environ.get("RUNWAY_WEBHOOK_URL", "")
    if not (url and items):
        return False
    body = json.dumps(_webhook_payload(items)).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 - a failed ping must not fail the run
        log.warning("webhook failed: %s", exc)
        return False


def send_email(items: list[Scored], profile: Profile) -> bool:
    """SMTP via env: RUNWAY_SMTP_HOST/PORT/USER/PASS, RUNWAY_EMAIL_TO."""
    host = os.environ.get("RUNWAY_SMTP_HOST")
    to = os.environ.get("RUNWAY_EMAIL_TO")
    if not (host and to and items):
        return False

    msg = EmailMessage()
    msg["Subject"] = f"Runway: {len(items)} new internship match{'es' if len(items) != 1 else ''}"
    msg["From"] = os.environ.get("RUNWAY_EMAIL_FROM", os.environ.get("RUNWAY_SMTP_USER", to))
    msg["To"] = to
    msg.set_content(render_terminal(items, profile))
    msg.add_alternative(render_html(items, profile), subtype="html")

    try:
        port = int(os.environ.get("RUNWAY_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            user = os.environ.get("RUNWAY_SMTP_USER")
            password = os.environ.get("RUNWAY_SMTP_PASS")
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("email failed: %s", exc)
        return False


def notify(items: list[Scored], profile: Profile) -> list[str]:
    """Fire every configured channel. Returns the ones that succeeded."""
    sent = []
    if send_webhook(items):
        sent.append("webhook")
    if send_email(items, profile):
        sent.append("email")
    return sent
