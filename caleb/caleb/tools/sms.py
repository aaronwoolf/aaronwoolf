"""Twilio SMS: nudges, reminders, and the daily brief.

send_to_user is policy-level `allow` (messages to the user themselves).
Anything outbound to a third party goes through the agent + approval gate,
never through this module directly.
"""
from __future__ import annotations

import os

from .. import db
from ..policy import evaluate


def _twilio_client():
    from twilio.rest import Client
    return Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])


def send_to_user(con, cfg, body: str) -> None:
    decision = evaluate("send_sms_to_user", cfg.approval_policy, draft_text=body)
    if decision.verdict != "allow":
        db.journal(con, cfg.user_ref, "system", "sms_blocked",
                   {"reason": decision.reason, "body": body}, decision.verdict)
        return

    user = con.execute("SELECT * FROM users WHERE id=?", (cfg.user_ref,)).fetchone()
    if not user or not user["phone"]:
        db.journal(con, cfg.user_ref, "system", "sms_skipped", {"reason": "no phone on file"})
        return

    _twilio_client().messages.create(
        to=user["phone"],
        from_=os.environ["TWILIO_FROM_NUMBER"],
        body=body[:480],  # keep briefs one-segment-ish and senior-readable
    )
    db.journal(con, cfg.user_ref, "agent", "send_sms_to_user", {"body": body})


def reminder_text(item: dict) -> str:
    appt = item["appt"]
    when = appt["starts_at"].replace("T", " at ")[:19]
    if item["stage"] == "t24_sms":
        return f"Reminder from Caleb: you have {appt['provider']} tomorrow, {when}. Reply OK to confirm."
    return f"Caleb here — {appt['provider']} is coming up today, {when}. Reply OK if you're set."
