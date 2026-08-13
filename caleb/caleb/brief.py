"""Daily brief: one SMS (later: one phone call) summarizing the day.

Blueprint rules honored here:
- Quarantined mail is counted, never quoted.
- The brief is short, warm, and one message long.
"""
from __future__ import annotations

from . import db
from .tools import sms


def build(con, cfg) -> str:
    uid = cfg.user_ref
    counts = dict(con.execute(
        "SELECT category, COUNT(*) FROM email_state "
        "WHERE user_id=? AND date(updated_at)=date('now') GROUP BY category",
        (uid,),
    ).fetchall())

    appts = con.execute(
        "SELECT provider, starts_at FROM appointments "
        "WHERE user_id=? AND date(starts_at)=date('now') AND status='scheduled'",
        (uid,),
    ).fetchall()

    parts = ["Good morning! Caleb here."]
    if appts:
        for a in appts:
            parts.append(f"Today: {a['provider']} at {a['starts_at'][11:16]}.")
    action = counts.get("Action-Needed", 0)
    if action:
        parts.append(f"{action} email{'s' if action != 1 else ''} need a decision — call me and I'll read them to you.")
    scams = counts.get("Suspected-Scam", 0)
    if scams:
        parts.append(f"I blocked {scams} message{'s' if scams != 1 else ''} that looked like scams. Nothing you need to do.")
    if len(parts) == 1:
        parts.append("Quiet day — nothing needs you. Enjoy it.")
    return " ".join(parts)


def send(con, cfg) -> None:
    text = build(con, cfg)
    sms.send_to_user(con, cfg, text)
    db.journal(con, cfg.user_ref, "agent", "daily_brief", {"text": text})
