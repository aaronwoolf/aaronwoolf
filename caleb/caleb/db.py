"""SQLite bootstrap and the append-only journal.

Usage:  python -m caleb.db init
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "caleb.sqlite3"
SCHEMA = ROOT / "db" / "schema.sql"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init() -> None:
    con = connect()
    con.executescript(SCHEMA.read_text())
    con.commit()
    print(f"initialized {DB_PATH}")


def journal(con: sqlite3.Connection, user_id: str, actor: str, action: str,
            payload: dict, approval_state: str = "n/a") -> None:
    """Every side effect and every decision writes exactly one row here."""
    con.execute(
        "INSERT INTO journal (user_id, actor, action, payload, approval_state) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, actor, action, json.dumps(payload, default=str), approval_state),
    )
    con.commit()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init()
    else:
        print("usage: python -m caleb.db init")
