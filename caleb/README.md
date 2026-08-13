# Caleb — a phone-first AI assistant for older adults

Caleb is a personal AI guardian: it triages email, calls and texts its user,
manages reminders and appointments, explains medical results in plain language,
watches for scams, and escalates emergencies up a configurable ladder
(rouse → front desk → family → human-dispatched 911).

Full product & architecture blueprint:
https://claude.ai/code/artifact/c6e31d8d-8172-4c88-a908-f2e62c28d6d1

This directory is the **week-1 skeleton** from the blueprint's build order:
single user, SQLite, Gmail observe-mode (L0), reminder engine, daily SMS brief.
Voice, health portals, and multi-user come later — the schema and config are
multi-tenant from day one so nothing needs rewriting.

## Layout

```
caleb/
├── config/caleb.assistant.yaml   # persona + channels + approval policy (the registry row)
├── db/schema.sql                 # users, contacts, meds, bills, appointments, journal
├── caleb/
│   ├── registry.py               # load/validate assistant configs
│   ├── db.py                     # SQLite bootstrap + journal writes
│   ├── policy.py                 # approval gates + hard denylist (enforced in code)
│   ├── agent.py                  # Claude Agent SDK session wrapper w/ PreToolUse gate
│   ├── heartbeat.py              # cron tick: build pending queue, wake agent if non-empty
│   ├── brief.py                  # daily brief assembly
│   ├── approvals.py               # park an action → text the user → yes/no → run or drop
│   ├── cli.py                     # onboarding: add-user/contact/medication/appointment
│   └── tools/
│       ├── gmail_client.py       # all Gmail API traffic: auth, labels, fetch, modify
│       ├── gmail_observe.py      # L0: classify + label under Caleb/, never act
│       └── sms.py                # Twilio send + approval replies
├── scripts/gmail_auth.py         # one-time OAuth flow; prints GMAIL_REFRESH_TOKEN
├── tests/                        # pytest — policy gate, brief text, CLI/journal
└── .env.example
```

## Setup (v0, single user = you)

1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in keys (Anthropic, Twilio, Google OAuth).
   Use a Google Workspace account with an **Internal** OAuth app to skip
   restricted-scope verification during self-test.
4. `python -m caleb.db init` — creates `caleb.sqlite3` from `db/schema.sql`.
5. Onboard yourself (no more hand-written SQL):
   ```
   python -m caleb.cli init-user aaron --name "Aaron Woolf" --phone +1555...
   python -m caleb.cli add-contact aaron --name "Jane Woolf" --relation daughter \
       --phone +1555... --trusted
   python -m caleb.cli add-medication aaron --drug Lisinopril --dose 10mg --schedule "daily 8am"
   python -m caleb.cli add-appointment aaron --provider "Dr. Chen" --starts-at 2026-08-05T14:00:00
   python -m caleb.cli list aaron
   ```
6. Cron (the BaddieBroker autopilot pattern):
   `*/15 * * * *  cd .../caleb && .venv/bin/python -m caleb.heartbeat`
7. `pytest` — runs the policy-gate, brief, and CLI/journal tests against an
   in-memory DB (no credentials needed).

## Autonomy rules (do not relax casually)

- Email starts at **L0 (observe)**: label only, zero outbound anything.
- The denylist in `policy.py` is enforced in code, not in the prompt:
  money movement, legal/medical consent, password/2FA flows, replies to
  quarantined senders, and **changes to Caleb's own config or contacts**
  always require a live human approval.
- Every action — every send, call, label, booking — writes a `journal` row.
- **Silence is never consent.** An `ask` verdict parks the action in `approvals`
  and texts the user a plain-language summary. It runs only on an explicit yes;
  an ambivalent reply ("yes but actually no") is treated as a no; anything
  unanswered for 48h is expired by the heartbeat and never sent.
