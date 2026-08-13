from caleb.brief import build


class FakeCfg:
    user_ref = "aaron"


def test_quiet_day_brief_when_nothing_pending(con):
    text = build(con, FakeCfg())
    assert "Quiet day" in text


def test_brief_mentions_todays_appointment(con):
    con.execute(
        "INSERT INTO appointments (id, user_id, provider, starts_at, status) "
        "VALUES (?, ?, ?, datetime('now', '+2 hours'), 'scheduled')",
        ("a1", "aaron", "Dr. Chen"),
    )
    con.commit()
    text = build(con, FakeCfg())
    assert "Dr. Chen" in text


def test_brief_counts_scam_quarantine_without_quoting_content(con):
    con.execute(
        "INSERT INTO email_state (user_id, message_id, category, state) "
        "VALUES (?, ?, 'Suspected-Scam', 'quarantined')",
        ("aaron", "m1"),
    )
    con.commit()
    text = build(con, FakeCfg())
    assert "1 message" in text and "blocked" in text
