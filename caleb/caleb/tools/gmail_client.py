"""Thin Gmail API wrapper: auth, label management, fetch, and modify.

All Gmail traffic for Caleb goes through here so the rest of the code
never touches googleapiclient directly. Scope is gmail.modify — Caleb can
read, label, and archive; it cannot permanently delete anything.
"""
from __future__ import annotations

import os
from functools import lru_cache

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .. import env  # noqa: F401  (loads .env)

CALEB_LABELS = [
    "Caleb/Family", "Caleb/Medical", "Caleb/Bills", "Caleb/Gov-Legal",
    "Caleb/Action-Needed", "Caleb/FYI", "Caleb/Newsletters", "Caleb/Promos",
    "Caleb/Suspected-Scam",
    "Caleb/State/Triaged", "Caleb/State/Quarantined",
]


def _credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/gmail.modify"],
    )


def service():
    return build("gmail", "v1", credentials=_credentials(), cache_discovery=False)


@lru_cache(maxsize=1)
def label_ids() -> dict[str, str]:
    """Map label name -> id, creating any missing Caleb/* labels."""
    svc = service()
    existing = {
        l["name"]: l["id"]
        for l in svc.users().labels().list(userId="me").execute().get("labels", [])
    }
    for name in CALEB_LABELS:
        if name not in existing:
            created = svc.users().labels().create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            ).execute()
            existing[name] = created["id"]
    return existing


def fetch_untriaged(max_results: int = 25) -> list[dict]:
    """Messages from the last day that Caleb hasn't triaged yet."""
    svc = service()
    resp = svc.users().messages().list(
        userId="me",
        q='newer_than:1d -label:"Caleb/State/Triaged" -label:"Caleb/State/Quarantined" -in:sent -in:draft',
        maxResults=max_results,
    ).execute()
    out = []
    for ref in resp.get("messages", []):
        msg = svc.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["From", "Subject"],
        ).execute()
        headers = {h["name"].lower(): h["value"]
                   for h in msg.get("payload", {}).get("headers", [])}
        out.append({
            "id": msg["id"],
            "thread_id": msg.get("threadId"),
            "sender": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "snippet": msg.get("snippet", ""),
        })
    return out


def apply_labels(message_id: str, category: str, state: str) -> None:
    ids = label_ids()
    state_label = "Caleb/State/Quarantined" if state == "quarantined" else "Caleb/State/Triaged"
    add = [ids[f"Caleb/{category}"], ids[state_label]]
    service().users().messages().modify(
        userId="me", id=message_id, body={"addLabelIds": add},
    ).execute()
