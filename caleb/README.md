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
│   └── tools/
│       ├── gmail_client.py       # all Gmail API traffic: auth, labels, fetch, modify
│       ├── gmail_observe.py      # L0: classify + label under Caleb/, never act
│       └── sms.py                # Twilio send + approval replies
├── scripts/gmail_auth.py         # one-time OAuth flow; prints GMAIL_REFRESH_TOKEN
└── .env.example
```

## Setup (v0, single user = you)

1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in keys (Anthropic, Twilio, Google OAuth).
   Use a Google Workspace account with an **Internal** OAuth app to skip
   restricted-scope verification during self-test.
4. `python -m caleb.db init` — creates `caleb.sqlite3` from `db/schema.sql`.
5. Cron (the BaddieBroker autopilot pattern):
   `*/15 * * * *  cd .../caleb && .venv/bin/python -m caleb.heartbeat`

## Autonomy rules (do not relax casually)

- Email starts at **L0 (observe)**: label only, zero outbound anything.
- The denylist in `policy.py` is enforced in code, not in the prompt:
  money movement, legal/medical consent, password/2FA flows, replies to
  quarantined senders, and **changes to Caleb's own config or contacts**
  always require a live human approval.
- Every action — every send, call, label, booking — writes a `journal` row.
