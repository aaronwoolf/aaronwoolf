import json

import pytest

from caleb import approvals


class FakeCfg:
    user_ref = "aaron"
    approval_policy = {"send_sms_to_user": "allow", "send_email": "ask"}


@pytest.fixture
def cfg(monkeypatch):
    # Don't touch Twilio in tests — capture the outbound nudge instead.
    sent = []
    monkeypatch.setattr(
        "caleb.tools.sms.send_to_user",
        lambda con, cfg, body: sent.append(body),
    )
    c = FakeCfg()
    c.sent = sent
    return c


# --- reply parsing: must be forgiving for an 80-year-old typing on a flip phone


@pytest.mark.parametrize("text", [
    "yes", "Yes", "YES", "yeah", "yep", "ok", "Okay", "sure", "y",
    "send it", "go ahead", "sounds good", "yes please send it",
])
def test_affirmatives(text):
    assert approvals.parse_reply(text) == "approved"


@pytest.mark.parametrize("text", [
    "no", "No", "nope", "nah", "n", "don't", "dont send", "stop",
    "cancel", "not now", "never mind", "wait",
])
def test_negatives(text):
    assert approvals.parse_reply(text) == "declined"


@pytest.mark.parametrize("text", ["what?", "who is this", "", "call me"])
def test_unclear_is_none(text):
    assert approvals.parse_reply(text) is None


def test_no_beats_yes_when_ambivalent():
    # "yes but no" must never send. Ambiguity fails closed.
    assert approvals.parse_reply("yes but actually no") == "declined"


def test_substring_does_not_false_trigger():
    # "nothing"/"yesterday" must not be read as no/yes.
    assert approvals.parse_reply("nothing happened yesterday") is None


# --- the lifecycle


def test_create_parks_and_notifies(con, cfg):
    aid = approvals.create(con, cfg, "send_email", "I wrote back to Dr. Chen.", {"to": "x@y.com"})
    rows = approvals.pending(con, "aaron")
    assert len(rows) == 1 and rows[0]["id"] == aid
    assert rows[0]["state"] == "pending"
    assert "Reply YES" in cfg.sent[0]


def test_yes_resolves_and_returns_payload(con, cfg):
    approvals.create(con, cfg, "send_email", "Reply to Dr. Chen?", {"to": "x@y.com"})
    got = approvals.resolve_from_reply(con, cfg, "yes")
    assert got is not None
    assert got["payload"] == {"to": "x@y.com"}
    assert approvals.pending(con, "aaron") == []


def test_no_resolves_without_payload(con, cfg):
    approvals.create(con, cfg, "send_email", "Reply to Dr. Chen?", {"to": "x@y.com"})
    assert approvals.resolve_from_reply(con, cfg, "no") is None
    assert approvals.pending(con, "aaron") == []
    state = con.execute("SELECT state FROM approvals").fetchone()["state"]
    assert state == "declined"


def test_unclear_reply_leaves_it_pending(con, cfg):
    approvals.create(con, cfg, "send_email", "Reply to Dr. Chen?", {"to": "x@y.com"})
    assert approvals.resolve_from_reply(con, cfg, "who is this?") is None
    assert len(approvals.pending(con, "aaron")) == 1  # still waiting


def test_oldest_pending_resolves_first(con, cfg):
    first = approvals.create(con, cfg, "send_email", "First", {"n": 1})
    approvals.create(con, cfg, "place_call", "Second", {"n": 2})
    got = approvals.resolve_from_reply(con, cfg, "yes")
    assert got["id"] == first
    assert len(approvals.pending(con, "aaron")) == 1


def test_silence_expires_and_never_sends(con, cfg):
    approvals.create(con, cfg, "send_email", "Reply to Dr. Chen?", {"to": "x@y.com"})
    con.execute("UPDATE approvals SET created_at = datetime('now', '-49 hours')")
    con.commit()
    assert approvals.expire_stale(con, cfg) == 1
    assert approvals.pending(con, "aaron") == []
    assert con.execute("SELECT state FROM approvals").fetchone()["state"] == "expired"


def test_fresh_approval_survives_expiry_sweep(con, cfg):
    approvals.create(con, cfg, "send_email", "Reply to Dr. Chen?", {"to": "x@y.com"})
    assert approvals.expire_stale(con, cfg) == 0
    assert len(approvals.pending(con, "aaron")) == 1


def test_every_transition_is_journaled(con, cfg):
    approvals.create(con, cfg, "send_email", "Reply to Dr. Chen?", {"to": "x@y.com"})
    approvals.resolve_from_reply(con, cfg, "yes")
    actions = [r["action"] for r in con.execute(
        "SELECT action FROM journal WHERE user_id='aaron' ORDER BY id").fetchall()]
    assert "approval_requested" in actions
    assert "approval_approved" in actions
