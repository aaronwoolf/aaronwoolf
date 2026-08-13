"""The approval loop — how a parked action becomes a sent one.

This is the machinery behind email level L2 ("draft, then ask") and behind
every `ask` verdict in policy.py. Nothing here can approve anything on its
own: an approval only resolves when a human reply arrives.

Flow:
    agent wants to send_email
      -> policy.evaluate returns "ask"
      -> approvals.create()  parks it, texts the user a plain-language summary
      -> user replies "yes" / "no" / says it on a call
      -> approvals.resolve_from_reply()  marks it and returns the payload to run
      -> heartbeat expires anything unanswered after 48h (silence never sends)
"""
from __future__ import annotations

import json
import re
import uuid

from . import db

EXPIRY_HOURS = 48

# Deliberately generous — an 80-year-old will not type "AFFIRMATIVE".
_YES = re.compile(
    r"\b(yes+|yeah|yep|yup|ya|ok|okay|okey|sure|fine|correct|right|"
    r"do it|send it|send|go ahead|go|please do|sounds good|that.s fine|y)\b",
    re.I,
)
_NO = re.compile(
    r"\b(no+|nope|nah|n|don.t|dont|do not|stop|cancel|wait|hold off|"
    r"not now|never mind|nevermind|skip)\b",
    re.I,
)


def parse_reply(text: str) -> str | None:
    """Map a free-text reply to 'approved' | 'declined' | None (unclear).

    A "no" anywhere in the message wins over a "yes" — if the user is
    ambivalent, Caleb does not act.
    """
    if not text:
        return None
    if _NO.search(text):
        return "declined"
    if _YES.search(text):
        return "approved"
    return None


def create(con, cfg, action: str, summary: str, payload: dict) -> str:
    """Park an action and ask the user. Returns the approval id."""
    from .tools import sms

    aid = uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO approvals (id, user_id, action, summary, payload) VALUES (?, ?, ?, ?, ?)",
        (aid, cfg.user_ref, action, summary, json.dumps(payload, default=str)),
    )
    con.commit()
    db.journal(con, cfg.user_ref, "agent", "approval_requested",
               {"approval_id": aid, "action": action, "summary": summary}, "pending")

    sms.send_to_user(con, cfg, f"{summary} Reply YES to go ahead, or NO to skip. — Caleb")
    return aid


def pending(con, user_id: str) -> list[dict]:
    rows = con.execute(
        "SELECT * FROM approvals WHERE user_id=? AND state='pending' ORDER BY created_at",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def resolve_from_reply(con, cfg, text: str, channel: str = "sms") -> dict | None:
    """Apply a user's reply to their oldest pending approval.

    Returns the approval (with payload decoded) when approved — the caller
    then executes it. Returns None when declined, unclear, or nothing pending.
    """
    verdict = parse_reply(text)
    items = pending(con, cfg.user_ref)
    if not items:
        return None
    if verdict is None:
        db.journal(con, cfg.user_ref, "human", "approval_reply_unclear",
                   {"text": text, "approval_id": items[0]["id"]}, "pending")
        return None

    item = items[0]
    con.execute(
        "UPDATE approvals SET state=?, resolved_at=datetime('now'), channel=? WHERE id=?",
        (verdict, channel, item["id"]),
    )
    con.commit()
    db.journal(con, cfg.user_ref, "human", f"approval_{verdict}",
               {"approval_id": item["id"], "action": item["action"], "text": text}, verdict)

    if verdict != "approved":
        return None
    item["payload"] = json.loads(item["payload"])
    return item


def expire_stale(con, cfg, hours: int = EXPIRY_HOURS) -> int:
    """Silence is not consent. Anything unanswered past the window dies."""
    rows = con.execute(
        "SELECT id, action FROM approvals WHERE user_id=? AND state='pending' "
        "AND created_at < datetime('now', ?)",
        (cfg.user_ref, f"-{hours} hours"),
    ).fetchall()
    for r in rows:
        con.execute(
            "UPDATE approvals SET state='expired', resolved_at=datetime('now') WHERE id=?",
            (r["id"],),
        )
        db.journal(con, cfg.user_ref, "system", "approval_expired",
                   {"approval_id": r["id"], "action": r["action"], "after_hours": hours}, "expired")
    con.commit()
    return len(rows)
