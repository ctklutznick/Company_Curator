"""Tests for database layer."""

from company_curator.data.db import Database


def test_create_tables(db):
    """Tables should be created on connect."""
    result = db.session.execute(
        __import__("sqlalchemy").text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    tables = {row[0] for row in result}
    assert "users" in tables
    assert "watchlist" in tables
    assert "daily_picks" in tables


def test_compatibility_layer(db, test_user):
    """Raw SQL compatibility should work."""
    db.execute(
        "INSERT INTO watchlist (user_id, ticker, company_name, added_date, entry_price) VALUES (?, ?, ?, ?, ?)",
        (test_user.id, "AAPL", "Apple", "2024-01-01", 150.0),
    )
    db.commit()

    row = db.fetchone("SELECT * FROM watchlist WHERE ticker = ?", ("AAPL",))
    assert row is not None
    assert row["ticker"] == "AAPL"

    rows = db.fetchall("SELECT * FROM watchlist WHERE user_id = ?", (test_user.id,))
    assert len(rows) == 1


def test_param_conversion():
    """'?' placeholders should convert to ':paramN'."""
    sql, params = Database._convert_params(
        "SELECT * FROM t WHERE a = ? AND b = ?", (1, "x")
    )
    assert ":p0" in sql
    assert ":p1" in sql
    assert params == {"p0": 1, "p1": "x"}
