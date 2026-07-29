"""Shared fixtures: an isolated, seeded SQLite DB per test."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(SCHEMA.read_text())
    c.execute(
        "INSERT INTO users (id, name, phone, pref_channel) VALUES (?, ?, ?, ?)",
        ("aaron", "Aaron Woolf", "+15551234567", "sms"),
    )
    c.commit()
    yield c
    c.close()
