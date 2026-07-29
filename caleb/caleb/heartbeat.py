"""The cron tick — BaddieBroker's autopilot loop, generalized.

Every N minutes, per user: assemble what's pending (new mail, due reminders,
expiring approvals) and wake the agent only if the queue is non-empty.
Idle users cost nothing.

Cron:  */15 * * * *  cd .../caleb && .venv/bin/python -m caleb.heartbeat
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import brief, db
from .registry import load_all
from .tools import gmail_observe, sms

BRIEF_HOUR_UTC = 15  # ~8am PT; per-user preference lands with the users table


def pending_reminders(con, user_id: str) -> list[dict]:
    """Appointments needing their next escalation stage. DB is source of truth."""
    now = datetime.utcnow()
    rows = con.execute(
        "SELECT * FROM appointments WHERE user_id=? AND status='scheduled'",
        (user_id,),
    ).fetchall()
    due = []
    for r in rows:
        starts = datetime.fromisoformat(r["starts_at"])
        stage = r["last_stage"]
        if stage is None and starts - now <= timedelta(hours=24):
            due.append({"appt": dict(r), "stage": "t24_sms"})
        elif stage == "t24_sms" and starts - now <= timedelta(hours=2):
            due.append({"appt": dict(r), "stage": "t2_sms"})
        # t30_call stage arrives with the voice layer (week 3-4)
    return due


def tick() -> None:
    for cfg in load_all():
        con = db.connect()
        uid = cfg.user_ref
        work: dict = {}

        if cfg.channels.get("email"):
            new_mail = gmail_observe.observe(con, cfg)   # L0: classify + label only
            if new_mail:
                work["mail"] = new_mail

        reminders = pending_reminders(con, uid)
        for item in reminders:
            body = sms.reminder_text(item)
            sms.send_to_user(con, cfg, body)
            con.execute(
                "UPDATE appointments SET last_stage=? WHERE id=?",
                (item["stage"], item["appt"]["id"]),
            )
            con.commit()

        # one brief per day, on the first tick after the brief hour
        now = datetime.utcnow()
        if now.hour >= BRIEF_HOUR_UTC:
            sent_today = con.execute(
                "SELECT 1 FROM journal WHERE user_id=? AND action='daily_brief' "
                "AND date(ts)=date('now') LIMIT 1", (uid,),
            ).fetchone()
            if not sent_today:
                brief.send(con, cfg)

        db.journal(con, uid, "system", "heartbeat",
                   {"mail": len(work.get("mail", [])), "reminders": len(reminders)})
        con.close()


if __name__ == "__main__":
    tick()
