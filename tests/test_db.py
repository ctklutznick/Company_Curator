"""Tests for database layer."""

from sqlalchemy import create_engine, inspect, text

from company_curator.data.db import Database


def test_connect_adds_missing_columns_to_existing_table(tmp_path):
    """connect() must add model columns missing from a pre-existing table.

    The app builds schema with create_all(), which never alters existing tables,
    so an older DB (e.g. one created before the ToS columns) would otherwise be
    missing them and every User query would fail.
    """
    url = f"sqlite:///{tmp_path}/old.db"
    engine = create_engine(url)
    with engine.begin() as conn:
        # Simulate an old users table missing the ToS (and SMTP) columns.
        conn.execute(text(
            "CREATE TABLE users ("
            "id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL, "
            "password_hash VARCHAR(255) NOT NULL, display_name VARCHAR(100) NOT NULL, "
            "created_at DATETIME NOT NULL)"
        ))
    engine.dispose()

    db = Database(url)
    db.connect()
    try:
        cols = {c["name"] for c in inspect(db.engine).get_columns("users")}
        assert "terms_accepted_at" in cols
        assert "terms_version" in cols
        # A query that references the new columns must now succeed.
        db.session.execute(text("SELECT terms_accepted_at FROM users"))
    finally:
        db.close()


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
