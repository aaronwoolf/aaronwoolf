from caleb import db


def test_init_user_then_query(con):
    row = con.execute("SELECT * FROM users WHERE id=?", ("aaron",)).fetchone()
    assert row["name"] == "Aaron Woolf"


def test_add_contact_trusted_flag(con):
    con.execute(
        "INSERT INTO contacts (id, user_id, name, relation, is_trusted, can_receive_alerts) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("c1", "aaron", "Jane Woolf", "daughter", 1, 1),
    )
    con.commit()
    c = con.execute("SELECT * FROM contacts WHERE user_id=?", ("aaron",)).fetchone()
    assert c["is_trusted"] == 1
    assert c["can_receive_alerts"] == 1


def test_journal_records_every_action(con):
    db.journal(con, "aaron", "human", "add_contact", {"name": "Jane"})
    rows = con.execute("SELECT * FROM journal WHERE user_id=?", ("aaron",)).fetchall()
    assert len(rows) == 1
    assert rows[0]["action"] == "add_contact"
    assert rows[0]["actor"] == "human"
