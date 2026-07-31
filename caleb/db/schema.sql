-- Caleb v0 schema. SQLite now, Postgres later — every table carries user_id
-- so multi-tenancy is a connection-string change, not a migration.

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,          -- matches user_ref in the assistant yaml
  name          TEXT NOT NULL,
  dob           TEXT,
  tz            TEXT NOT NULL DEFAULT 'America/Los_Angeles',
  phone         TEXT,
  email         TEXT,
  pref_channel  TEXT NOT NULL DEFAULT 'sms'   -- sms | voice
);

CREATE TABLE IF NOT EXISTS profile_facts (
  user_id     TEXT NOT NULL REFERENCES users(id),
  key         TEXT NOT NULL,
  value       TEXT NOT NULL,
  confidence  REAL NOT NULL DEFAULT 1.0,
  source      TEXT,                        -- onboarding | agent | caregiver
  updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS contacts (
  id                TEXT PRIMARY KEY,
  user_id           TEXT NOT NULL REFERENCES users(id),
  name              TEXT NOT NULL,
  relation          TEXT,
  phone             TEXT,
  email             TEXT,
  is_trusted        INTEGER NOT NULL DEFAULT 0,  -- may receive safety alerts
  can_receive_alerts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS medications (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id),
  drug       TEXT NOT NULL,
  dose       TEXT,
  schedule   TEXT,                         -- cron-ish or free text for v0
  prescriber TEXT,
  pharmacy   TEXT,
  refill_due TEXT
);

CREATE TABLE IF NOT EXISTS recurring_bills (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  payee       TEXT NOT NULL,
  amount_est  REAL,
  due_day     INTEGER,
  autopay     INTEGER NOT NULL DEFAULT 0,
  portal_url  TEXT
);

-- The DB is the source of truth for time; Google Calendar is a projection.
CREATE TABLE IF NOT EXISTS appointments (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users(id),
  provider    TEXT NOT NULL,
  starts_at   TEXT NOT NULL,
  location    TEXT,
  prep_notes  TEXT,
  status      TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled|confirmed|done|cancelled
  -- escalation state machine; idempotency key is (id, stage)
  last_stage  TEXT                                -- t24_sms | t2_sms | t30_call | family
);

-- Direct descendant of the BaddieBroker trade journal. Append-only.
CREATE TABLE IF NOT EXISTS journal (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        TEXT NOT NULL,
  ts             TEXT NOT NULL DEFAULT (datetime('now')),
  actor          TEXT NOT NULL,            -- agent | human | system
  action         TEXT NOT NULL,            -- tool name or event type
  payload        TEXT NOT NULL,            -- JSON
  approval_state TEXT                      -- n/a | pending | approved | declined | expired
);

-- Parked actions waiting on a human "yes". The journal records the events
-- (append-only); this table holds the mutable state of the request itself.
CREATE TABLE IF NOT EXISTS approvals (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  action      TEXT NOT NULL,            -- send_email, place_call, book_appointment...
  summary     TEXT NOT NULL,            -- plain-language line read/texted to the user
  payload     TEXT NOT NULL,            -- JSON: the exact tool args to run on approval
  state       TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|declined|expired
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  resolved_at TEXT,
  channel     TEXT                      -- sms | voice — how the yes/no arrived
);

CREATE INDEX IF NOT EXISTS idx_approvals_pending ON approvals(user_id, state, created_at);

-- Email pipeline state (mirrors the Caleb/State/* Gmail labels).
CREATE TABLE IF NOT EXISTS email_state (
  user_id    TEXT NOT NULL,
  message_id TEXT NOT NULL,                -- Gmail message id
  thread_id  TEXT,
  category   TEXT,                         -- Family|Medical|Bills|Gov-Legal|Action-Needed|FYI|Newsletters|Promos|Suspected-Scam
  state      TEXT NOT NULL DEFAULT 'new',  -- new|triaged|drafted|awaiting|sent|declined|expired|quarantined|escalated
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (user_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_journal_user_ts ON journal(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_email_state ON email_state(user_id, state);
