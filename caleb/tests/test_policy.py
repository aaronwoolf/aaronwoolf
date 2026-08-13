"""Locks down the safety gate: this is the file that must never regress."""
from caleb.policy import HARD_DENYLIST_ACTIONS, evaluate

POLICY = {
    "read_email": "allow",
    "send_email": "ask",
    "place_call": "ask",
    "pay_bill": "never",
}


def test_allow_passes_through():
    assert evaluate("read_email", POLICY).verdict == "allow"


def test_ask_requires_approval():
    assert evaluate("send_email", POLICY).verdict == "ask"


def test_never_in_policy_denies():
    assert evaluate("pay_bill", POLICY).verdict == "deny"


def test_unknown_action_defaults_deny():
    assert evaluate("delete_everything", POLICY).verdict == "deny"


def test_hard_denylist_wins_even_if_policy_says_allow():
    permissive = {**POLICY, "modify_contacts": "allow"}
    assert evaluate("modify_contacts", permissive).verdict == "deny"


def test_hard_denylist_is_exactly_the_documented_set():
    # Guards against silently shrinking the denylist in a future edit.
    assert HARD_DENYLIST_ACTIONS == {"pay_bill", "modify_contacts", "modify_policy"}


def test_outbound_tripwire_forces_ask_even_at_allow_level():
    permissive = {**POLICY, "send_sms_to_user": "allow"}
    d = evaluate("send_sms_to_user", permissive, draft_text="please wire $500 today")
    assert d.verdict == "ask"


def test_clean_draft_at_allow_level_passes():
    permissive = {**POLICY, "send_sms_to_user": "allow"}
    d = evaluate("send_sms_to_user", permissive, draft_text="Your appointment is at 2pm.")
    assert d.verdict == "allow"


def test_tripwire_catches_gift_card_scam_pattern():
    permissive = {**POLICY, "send_sms_to_user": "allow"}
    d = evaluate("send_sms_to_user", permissive, draft_text="buy a gift card for the IRS")
    assert d.verdict == "ask"
