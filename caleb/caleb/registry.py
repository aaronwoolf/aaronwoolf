"""Load assistant configs — the registry pattern from the trading fleet.

One YAML per end user in config/. v0 loads a single file; the productized
orchestrator iterates the directory exactly like the fleet iterated accounts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class AssistantConfig:
    user_ref: str
    persona: dict
    model: dict
    channels: dict
    approval_policy: dict
    email_autonomy: dict
    guardrails: dict
    heartbeat: str = "*/15 * * * *"
    raw: dict = field(default_factory=dict)


def load(path: Path | None = None) -> AssistantConfig:
    path = path or CONFIG_DIR / "caleb.assistant.yaml"
    data = yaml.safe_load(path.read_text())
    return AssistantConfig(
        user_ref=data["user_ref"],
        persona=data["persona"],
        model=data["model"],
        channels=data["channels"],
        approval_policy=data["approval_policy"],
        email_autonomy=data["email_autonomy"],
        guardrails=data["guardrails"],
        heartbeat=data.get("heartbeat", "*/15 * * * *"),
        raw=data,
    )


def load_all() -> list[AssistantConfig]:
    return [load(p) for p in sorted(CONFIG_DIR.glob("*.assistant.yaml"))]
