"""L0 email observation: classify and label, never act.

Runs from the heartbeat. Pulls messages since the last tick, classifies each
with the triage model, applies Caleb/* labels, and records state. Suspected
scams are labeled and quarantined in state — their content is never surfaced
verbatim to the user (blueprint rule: Caleb must not become the scam's
delivery vehicle).

Gmail auth: OAuth refresh token from a Workspace "Internal" app (see README).
Scope: gmail.modify only — Caleb can label and archive, never permanently delete.
"""
from __future__ import annotations

import json
import os

from anthropic import Anthropic

from .. import db

CATEGORIES = [
    "Family", "Medical", "Bills", "Gov-Legal", "Action-Needed",
    "FYI", "Newsletters", "Promos", "Suspected-Scam",
]

TRIAGE_PROMPT = """You are the email triage layer for Caleb, an assistant for an older adult.
Classify the email into exactly one category: {cats}.
Elder-scam patterns (grandchild emergency, sweepstakes, tech support, romance,
"Medicare card expiring", gift cards, wire/crypto urgency, lookalike bank domains)
are Suspected-Scam even when plausible-looking.
Reply with JSON only: {{"category": "...", "reason": "one short sentence"}}"""


def _classify(client: Anthropic, model: str, subject: str, sender: str, snippet: str) -> dict:
    msg = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": TRIAGE_PROMPT.format(cats=", ".join(CATEGORIES))
            + f"\n\nFrom: {sender}\nSubject: {subject}\nSnippet: {snippet}",
        }],
    )
    try:
        return json.loads(msg.content[0].text)
    except (json.JSONDecodeError, IndexError):
        return {"category": "FYI", "reason": "unparseable triage response"}


def observe(con, cfg) -> list[dict]:
    """Classify + label new mail. Returns the list of triaged items."""
    if not os.environ.get("GMAIL_REFRESH_TOKEN"):
        db.journal(con, cfg.user_ref, "system", "gmail_observe_skipped",
                   {"reason": "no GMAIL_REFRESH_TOKEN configured"})
        return []

    from . import gmail_client

    client = Anthropic()
    triage_model = cfg.model.get("triage", "claude-haiku-4-5")
    triaged: list[dict] = []

    for m in gmail_client.fetch_untriaged():
        verdict = _classify(client, triage_model, m["subject"], m["sender"], m["snippet"])
        state = "quarantined" if verdict["category"] == "Suspected-Scam" else "triaged"
        con.execute(
            "INSERT OR REPLACE INTO email_state (user_id, message_id, thread_id, category, state) "
            "VALUES (?, ?, ?, ?, ?)",
            (cfg.user_ref, m["id"], m.get("thread_id"), verdict["category"], state),
        )
        con.commit()
        gmail_client.apply_labels(m["id"], verdict["category"], state)
        db.journal(con, cfg.user_ref, "agent", "label_email",
                   {"message_id": m["id"], **verdict, "state": state})
        triaged.append({**m, **verdict, "state": state})
    return triaged
