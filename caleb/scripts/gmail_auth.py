"""One-time Gmail OAuth bootstrap.

Run this ON A MACHINE WITH A BROWSER (your desktop, not the droplet):

    python scripts/gmail_auth.py

It opens Google's consent screen for the account Caleb will manage
(use the Workspace account with the Internal OAuth app), then prints the
refresh token. Copy that value into GMAIL_REFRESH_TOKEN in the droplet's
.env — that's the only secret this flow produces.

Requires GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env or the environment.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from caleb import env  # noqa: F401  (loads .env)

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main() -> None:
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET first (see .env.example).")

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        SCOPES,
    )
    creds = flow.run_local_server(port=0, prompt="consent")
    print("\nAdd this line to the droplet's .env:\n")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
