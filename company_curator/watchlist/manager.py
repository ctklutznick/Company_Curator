"""Watchlist manager for adding, removing, and listing tracked companies.

SRP: Only manages watchlist CRUD operations.
DIP: Depends on Database abstraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from company_curator.data.db import Database


@dataclass
class WatchlistEntry:
    id: int
    ticker: str
    company_name: str
    added_date: str
    entry_price: float
    entry_revenue: float | None
    status: str
    notes: str | None


class WatchlistManager:
    """Manages the investment watchlist."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(
        self,
        ticker: str,
        company_name: str,
        entry_price: float,
        entry_revenue: float | None = None,
        notes: str | None = None,
    ) -> WatchlistEntry:
        """Add a company to the watchlist."""
        now = datetime.now().isoformat()
        self._db.execute(
            """INSERT INTO watchlist (ticker, company_name, added_date, entry_price, entry_revenue, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker.upper(), company_name, now, entry_price, entry_revenue, notes),
        )
        self._db.commit()

        row = self._db.fetchone("SELECT * FROM watchlist WHERE ticker = ?", (ticker.upper(),))
        return self._row_to_entry(row)

    def remove(self, ticker: str) -> bool:
        """Remove a company from the watchlist."""
        cursor = self._db.execute(
            "UPDATE watchlist SET status = 'removed' WHERE ticker = ? AND status = 'active'",
            (ticker.upper(),),
        )
        self._db.commit()
        return cursor.rowcount > 0

    def list_active(self) -> list[WatchlistEntry]:
        """List all active watchlist entries."""
        rows = self._db.fetchall(
            "SELECT * FROM watchlist WHERE status = 'active' ORDER BY added_date DESC"
        )
        return [self._row_to_entry(row) for row in rows]

    def get(self, ticker: str) -> WatchlistEntry | None:
        """Get a specific watchlist entry."""
        row = self._db.fetchone(
            "SELECT * FROM watchlist WHERE ticker = ? AND status = 'active'",
            (ticker.upper(),),
        )
        return self._row_to_entry(row) if row else None

    def exists(self, ticker: str) -> bool:
        """Check if a ticker is already on the watchlist."""
        row = self._db.fetchone(
            "SELECT 1 FROM watchlist WHERE ticker = ? AND status = 'active'",
            (ticker.upper(),),
        )
        return row is not None

    @staticmethod
    def _row_to_entry(row) -> WatchlistEntry:
        return WatchlistEntry(
            id=row["id"],
            ticker=row["ticker"],
            company_name=row["company_name"],
            added_date=row["added_date"],
            entry_price=row["entry_price"],
            entry_revenue=row["entry_revenue"],
            status=row["status"],
            notes=row["notes"],
        )
