"""The Caleb brain: a Claude Agent SDK session with the policy gate wired in.

This wrapper exists so that EVERY tool the model can call passes through
policy.evaluate() in a PreToolUse hook — deterministic, code-level gating
the model cannot argue with. Denied calls are journaled; "ask" calls park
an approval request instead of executing.

Week-1 scope: the agent handles ad-hoc requests (via CLI now, via SMS/voice
later). The heartbeat does not need the agent for L0 email — that's plain
classification. The agent enters the email path at L2 (draft-for-approval).

Verify hook/API names against the installed claude-agent-sdk version:
https://code.claude.com/docs/en/agent-sdk/python
"""
from __future__ import annotations

import asyncio
import json

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from . import db
from .policy import evaluate
from .registry import AssistantConfig


def system_prompt(cfg: AssistantConfig) -> str:
    p = cfg.persona
    return (
        f"You are {p['name']}, a personal assistant. Tone: {p['tone']}.\n"
        "Rules that always apply:\n"
        "- You explain; you never diagnose. For medical results: say what a test "
        "measures and what the note says, then prepare questions for the doctor. "
        "Chest pain, stroke signs, or overdose mentions: tell them to call 911, nothing else.\n"
        "- Never read or summarize quarantined (suspected-scam) messages verbatim.\n"
        "- When unsure whether an action needs approval, it needs approval.\n"
    )


def make_pre_tool_hook(cfg: AssistantConfig, con):
    """Gate every tool call through the approval policy."""

    async def pre_tool_use(input_data, tool_use_id, context):
        tool = input_data.get("tool_name", "")
        args = input_data.get("tool_input", {})
        draft = json.dumps(args) if args else None
        decision = evaluate(tool, cfg.approval_policy, draft_text=draft)

        if decision.verdict == "allow":
            return {}
        if decision.verdict == "ask":
            db.journal(con, cfg.user_ref, "agent", tool, {"args": args}, "pending")
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason":
                        "Parked for human approval (sent by SMS). Do not retry; "
                        "tell the user you've asked for their OK.",
                }
            }
        db.journal(con, cfg.user_ref, "agent", tool, {"args": args, "reason": decision.reason}, "denied")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Not permitted: {decision.reason}",
            }
        }

    return pre_tool_use


async def ask_caleb(cfg: AssistantConfig, con, message: str) -> str:
    """One turn with Caleb. CLI harness now; SMS/voice route here later."""
    options = ClaudeAgentOptions(
        model=cfg.model["main"],
        system_prompt=system_prompt(cfg),
        hooks={"PreToolUse": [make_pre_tool_hook(cfg, con)]},
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query(message)
        chunks = []
        async for msg in client.receive_response():
            text = getattr(msg, "text", None)
            if text:
                chunks.append(text)
        reply = "".join(chunks)
    db.journal(con, cfg.user_ref, "agent", "conversation", {"user": message, "caleb": reply})
    return reply


if __name__ == "__main__":
    import sys

    from .registry import load

    cfg = load()
    con = db.connect()
    prompt = " ".join(sys.argv[1:]) or "Introduce yourself in two sentences."
    print(asyncio.run(ask_caleb(cfg, con, prompt)))
