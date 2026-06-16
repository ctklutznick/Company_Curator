"""Monthly audit persistence layer.

SRP: Only responsible for saving and retrieving audit results.
DIP: Depends on Database abstraction.
"""

from __future__ import annotations

from datetime import datetime

from company_curator.analysis.watchlist_audit import AuditResult
from company_curator.data.db import Database
from company_curator.watchlist.manager import WatchlistManager


class AuditManager:
    """Persists monthly audit results and handles drop proposal responses."""

    def __init__(self, db: Database, user_id: int) -> None:
        self._db = db
        self._user_id = user_id

    def save_audit(self, audit_month: str, result: AuditResult) -> int:
        """Save an audit result to the database. Returns the audit ID."""
        now = datetime.now()
        audit_date = now.strftime("%Y-%m-%d")
        created_at = now.isoformat()

        self._db.execute(
            """INSERT OR REPLACE INTO monthly_audits
               (user_id, audit_date, audit_month, summary, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (self._user_id, audit_date, audit_month, result.summary, created_at),
        )
        self._db.commit()

        audit_row = self._db.fetchone(
            "SELECT id FROM monthly_audits WHERE user_id = ? AND audit_month = ?",
            (self._user_id, audit_month),
        )
        audit_id = audit_row["id"]

        self._db.execute(
            "DELETE FROM monthly_audit_entries WHERE audit_id = ?",
            (audit_id,),
        )

        all_stocks = (
            [(s, s.rank) for s in result.top_picks]
            + [(s, None) for s in result.holds]
            + [(s, None) for s in result.drops]
        )

        for stock, rank in all_stocks:
            self._db.execute(
                """INSERT INTO monthly_audit_entries
                   (audit_id, user_id, ticker, company_name, rank, score,
                    recommendation, reasoning, current_price, entry_price, price_change_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    audit_id, self._user_id, stock.ticker, stock.company_name,
                    rank, stock.score, stock.recommendation, stock.reasoning,
                    stock.current_price, stock.entry_price, stock.price_change_pct,
                ),
            )

        # Create alerts for drop proposals
        for stock in result.drops:
            self._db.execute(
                """INSERT INTO alerts (user_id, ticker, alert_type, message, triggered_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    self._user_id,
                    stock.ticker,
                    "audit_drop_proposal",
                    f"Monthly audit recommends dropping {stock.ticker} ({stock.company_name}): "
                    f"{stock.reasoning}",
                    created_at,
                ),
            )

        self._db.commit()
        return audit_id

    def get_latest(self) -> dict | None:
        """Get the most recent audit with its entries."""
        audit = self._db.fetchone(
            "SELECT * FROM monthly_audits WHERE user_id = ? ORDER BY audit_month DESC LIMIT 1",
            (self._user_id,),
        )
        if not audit:
            return None
        return self._load_audit_with_entries(audit)

    def get_by_month(self, audit_month: str) -> dict | None:
        """Get a specific audit by month (e.g. '2026-06')."""
        audit = self._db.fetchone(
            "SELECT * FROM monthly_audits WHERE user_id = ? AND audit_month = ?",
            (self._user_id, audit_month),
        )
        if not audit:
            return None
        return self._load_audit_with_entries(audit)

    def list_audits(self) -> list[dict]:
        """List all audits (summary only, no entries)."""
        rows = self._db.fetchall(
            "SELECT * FROM monthly_audits WHERE user_id = ? ORDER BY audit_month DESC",
            (self._user_id,),
        )
        return [dict(row) for row in rows]

    def respond_to_drop(self, entry_id: int, accepted: bool) -> None:
        """Accept or reject a drop proposal.

        If accepted, removes the stock from the watchlist.
        """
        status = 1 if accepted else 2
        entry = self._db.fetchone(
            "SELECT * FROM monthly_audit_entries WHERE id = ? AND user_id = ?",
            (entry_id, self._user_id),
        )
        if not entry:
            return

        self._db.execute(
            "UPDATE monthly_audit_entries SET drop_acknowledged = ? WHERE id = ? AND user_id = ?",
            (status, entry_id, self._user_id),
        )

        # Acknowledge the corresponding alert
        self._db.execute(
            """UPDATE alerts SET acknowledged = 1
               WHERE user_id = ? AND ticker = ? AND alert_type = 'audit_drop_proposal' AND acknowledged = 0""",
            (self._user_id, entry["ticker"]),
        )

        if accepted:
            manager = WatchlistManager(self._db, self._user_id)
            manager.remove(entry["ticker"])

        self._db.commit()

    def _load_audit_with_entries(self, audit) -> dict:
        entries = self._db.fetchall(
            "SELECT * FROM monthly_audit_entries WHERE audit_id = ? ORDER BY score DESC",
            (audit["id"],),
        )
        audit_dict = dict(audit)
        audit_dict["top_picks"] = [dict(e) for e in entries if e["recommendation"] == "top_pick"]
        audit_dict["holds"] = [dict(e) for e in entries if e["recommendation"] == "hold"]
        audit_dict["drops"] = [dict(e) for e in entries if e["recommendation"] == "drop"]
        audit_dict["top_picks"].sort(key=lambda x: x["rank"] or 999)
        return audit_dict
