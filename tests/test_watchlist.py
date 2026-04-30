"""Tests for watchlist operations with user isolation."""

from company_curator.watchlist.manager import WatchlistManager


def test_add_and_list(db, test_user):
    manager = WatchlistManager(db, test_user.id)
    entry = manager.add("AAPL", "Apple Inc.", 150.0)

    assert entry.ticker == "AAPL"
    assert entry.entry_price == 150.0

    entries = manager.list_active()
    assert len(entries) == 1
    assert entries[0].ticker == "AAPL"


def test_user_isolation(db, test_user):
    from flask_bcrypt import generate_password_hash

    from company_curator.data.models import User

    # Create second user
    user2 = User(
        email="user2@example.com",
        password_hash=generate_password_hash("password123").decode("utf-8"),
        display_name="User Two",
    )
    db.session.add(user2)
    db.session.commit()

    # Each user adds to their watchlist
    mgr1 = WatchlistManager(db, test_user.id)
    mgr2 = WatchlistManager(db, user2.id)

    mgr1.add("AAPL", "Apple Inc.", 150.0)
    mgr2.add("GOOGL", "Alphabet Inc.", 140.0)

    # Each user only sees their own
    assert len(mgr1.list_active()) == 1
    assert mgr1.list_active()[0].ticker == "AAPL"

    assert len(mgr2.list_active()) == 1
    assert mgr2.list_active()[0].ticker == "GOOGL"


def test_remove(db, test_user):
    manager = WatchlistManager(db, test_user.id)
    manager.add("TSLA", "Tesla Inc.", 200.0)

    assert manager.exists("TSLA")
    manager.remove("TSLA")
    assert not manager.exists("TSLA")
    assert len(manager.list_active()) == 0
