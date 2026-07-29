"""Approval policy and hard denylist.

This is the layer that makes Caleb safe to hand an inbox and a phone line.
It is enforced in code — the model never gets to talk its way past it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ALLOW, ASK, NEVER = "allow", "ask", "never"

# Actions that require a live human approval regardless of any config level.
# Mirrors the blueprint's "never autonomous" box.
HARD_DENYLIST_ACTIONS = {
    "pay_bill",
    "modify_contacts",
    "modify_policy",
}

# Outbound-content tripwires: if a draft matches these, force ASK even in an
# auto-send (L3) category, and flag the journal row for review.
OUTBOUND_TRIPWIRES = [
    re.compile(p, re.I)
    for p in (
        r"\b(wire|transfer|zelle|venmo|crypto|bitcoin|gift ?card)\b",
        r"\b(ssn|social security number|password|verification code|2fa|one[- ]time code)\b",
        r"\b(routing|account) number\b",
        r"\bpower of attorney\b",
    )
]


@dataclass
class Decision:
    action: str
    verdict: str          # allow | ask | deny
    reason: str


def evaluate(action: str, policy: dict, draft_text: str | None = None) -> Decision:
    """Gate one tool call. Called from the agent's PreToolUse hook."""
    if action in HARD_DENYLIST_ACTIONS:
        return Decision(action, "deny", "hard denylist: requires live human approval flow")

    level = policy.get(action, NEVER)  # unknown actions default to NEVER
    if level == NEVER:
        return Decision(action, "deny", f"policy: {action}=never")

    if draft_text:
        for pat in OUTBOUND_TRIPWIRES:
            if pat.search(draft_text):
                return Decision(action, "ask", f"tripwire matched: {pat.pattern}")

    if level == ASK:
        return Decision(action, "ask", "policy: requires approval")
    return Decision(action, "allow", "policy: allowed")
