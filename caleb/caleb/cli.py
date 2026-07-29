"""Onboarding CLI: populate a user's profile without hand-written SQL.

This is the "adult child fills in the form" step from the blueprint,
done at a terminal for v0. Usage:

    python -m caleb.cli init-user aaron --name "Aaron Woolf" --phone +15551234567
    python -m caleb.cli add-contact aaron --name "Jane Woolf" --relation daughter \
        --phone +15559876543 --trusted
    python -m caleb.cli add-medication aaron --drug Lisinopril --dose 10mg \
        --schedule "daily 8am"
    python -m caleb.cli add-appointment aaron --provider "Dr. Chen" \
        --starts-at 2026-08-05T14:00:00
    python -m caleb.cli list aaron
"""
from __future__ import annotations

import argparse
import sys
import uuid

from . import db


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def cmd_init_user(args) -> None:
    con = db.connect()
    con.execute(
        "INSERT INTO users (id, name, dob, tz, phone, email, pref_channel) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name, dob=excluded.dob, "
        "tz=excluded.tz, phone=excluded.phone, email=excluded.email, "
        "pref_channel=excluded.pref_channel",
        (args.user_id, args.name, args.dob, args.tz, args.phone, args.email, args.pref_channel),
    )
    con.commit()
    db.journal(con, args.user_id, "human", "init_user", {"name": args.name})
    print(f"user {args.user_id!r} ready ({args.name})")


def cmd_add_contact(args) -> None:
    con = db.connect()
    cid = _uid()
    con.execute(
        "INSERT INTO contacts (id, user_id, name, relation, phone, email, "
        "is_trusted, can_receive_alerts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (cid, args.user_id, args.name, args.relation, args.phone, args.email,
         int(args.trusted), int(args.alerts or args.trusted)),
    )
    con.commit()
    db.journal(con, args.user_id, "human", "add_contact", {"contact_id": cid, "name": args.name})
    print(f"contact {cid} added: {args.name} ({args.relation or 'no relation given'})")


def cmd_add_medication(args) -> None:
    con = db.connect()
    mid = _uid()
    con.execute(
        "INSERT INTO medications (id, user_id, drug, dose, schedule, prescriber, pharmacy) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mid, args.user_id, args.drug, args.dose, args.schedule, args.prescriber, args.pharmacy),
    )
    con.commit()
    db.journal(con, args.user_id, "human", "add_medication", {"med_id": mid, "drug": args.drug})
    print(f"medication {mid} added: {args.drug} {args.dose or ''}".strip())


def cmd_add_appointment(args) -> None:
    con = db.connect()
    aid = _uid()
    con.execute(
        "INSERT INTO appointments (id, user_id, provider, starts_at, location, prep_notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (aid, args.user_id, args.provider, args.starts_at, args.location, args.notes),
    )
    con.commit()
    db.journal(con, args.user_id, "human", "add_appointment",
               {"appt_id": aid, "provider": args.provider, "starts_at": args.starts_at})
    print(f"appointment {aid} added: {args.provider} at {args.starts_at}")


def cmd_list(args) -> None:
    con = db.connect()
    user = con.execute("SELECT * FROM users WHERE id=?", (args.user_id,)).fetchone()
    if not user:
        print(f"no such user {args.user_id!r}", file=sys.stderr)
        raise SystemExit(1)
    print(f"user: {user['name']} <{user['phone'] or user['email'] or 'no contact info'}>")
    for table, label in (("contacts", "contacts"), ("medications", "medications"),
                          ("appointments", "appointments")):
        rows = con.execute(f"SELECT * FROM {table} WHERE user_id=?", (args.user_id,)).fetchall()
        print(f"\n{label} ({len(rows)}):")
        for r in rows:
            print(" -", dict(r))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m caleb.cli")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init-user")
    s.add_argument("user_id")
    s.add_argument("--name", required=True)
    s.add_argument("--dob")
    s.add_argument("--tz", default="America/Los_Angeles")
    s.add_argument("--phone")
    s.add_argument("--email")
    s.add_argument("--pref-channel", dest="pref_channel", default="sms")
    s.set_defaults(func=cmd_init_user)

    s = sub.add_parser("add-contact")
    s.add_argument("user_id")
    s.add_argument("--name", required=True)
    s.add_argument("--relation")
    s.add_argument("--phone")
    s.add_argument("--email")
    s.add_argument("--trusted", action="store_true", help="may receive safety alerts")
    s.add_argument("--alerts", action="store_true", help="explicitly enable alerts without --trusted")
    s.set_defaults(func=cmd_add_contact)

    s = sub.add_parser("add-medication")
    s.add_argument("user_id")
    s.add_argument("--drug", required=True)
    s.add_argument("--dose")
    s.add_argument("--schedule")
    s.add_argument("--prescriber")
    s.add_argument("--pharmacy")
    s.set_defaults(func=cmd_add_medication)

    s = sub.add_parser("add-appointment")
    s.add_argument("user_id")
    s.add_argument("--provider", required=True)
    s.add_argument("--starts-at", required=True, help="ISO 8601, e.g. 2026-08-05T14:00:00")
    s.add_argument("--location")
    s.add_argument("--notes")
    s.set_defaults(func=cmd_add_appointment)

    s = sub.add_parser("list")
    s.add_argument("user_id")
    s.set_defaults(func=cmd_list)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
