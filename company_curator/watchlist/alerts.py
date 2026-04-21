"""Alert system for investment readiness notifications.

SRP: Only responsible for creating and managing alerts.
DIP: Depends on Database abstraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from company_curator.data.db import Database
from company_curator.watchlist.monitor import GrowthReport


@dataclass
class Alert:
    id: int
    ticker: str
    alert_type: str
    message: str
    triggered_date: str
    acknowledged: bool


class AlertManager:
    """Creates and manages investment alerts."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def check_and_create_alerts(self, reports: list[GrowthReport]) -> list[Alert]:
        """Check growth reports and create alerts for investment-ready companies."""
        new_alerts: list[Alert] = []

        for report in reports:
            if report.ready_for_investment:
                alert = self._create_investment_alert(report)
                if alert:
                    new_alerts.append(alert)

        return new_alerts

    def get_unacknowledged(self) -> list[Alert]:
        """Get all unacknowledged alerts."""
        rows = self._db.fetchall(
            "SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY triggered_date DESC"
        )
        return [self._row_to_alert(row) for row in rows]

    def acknowledge(self, alert_id: int) -> None:
        """Mark an alert as acknowledged."""
        self._db.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?",
            (alert_id,),
        )
        self._db.commit()

    def _create_investment_alert(self, report: GrowthReport) -> Alert | None:
        """Create an investment alert if one doesn't already exist."""
        existing = self._db.fetchone(
            """SELECT 1 FROM alerts
               WHERE ticker = ? AND alert_type = 'investment_ready' AND acknowledged = 0""",
            (report.ticker,),
        )
        if existing:
            return None

        now = datetime.now().isoformat()
        message = (
            f"{report.ticker} ({report.company_name}) is ready for investment consideration!\n"
            f"Watched for {report.days_watched} days.\n"
            f"Price: ${report.entry_price:.2f} -> ${report.current_price:.2f} "
            f"({report.price_change_pct:+.1f}%)\n"
        )
        if report.revenue_change_pct is not None:
            message += f"Revenue growth: {report.revenue_change_pct:+.1f}%"

        self._db.execute(
            """INSERT INTO alerts (ticker, alert_type, message, triggered_date)
               VALUES (?, ?, ?, ?)""",
            (report.ticker, "investment_ready", message, now),
        )
        self._db.commit()

        row = self._db.fetchone(
            "SELECT * FROM alerts WHERE ticker = ? ORDER BY id DESC LIMIT 1",
            (report.ticker,),
        )
        return self._row_to_alert(row) if row else None

    @staticmethod
    def _row_to_alert(row) -> Alert:
        return Alert(
            id=row["id"],
            ticker=row["ticker"],
            alert_type=row["alert_type"],
            message=row["message"],
            triggered_date=row["triggered_date"],
            acknowledged=bool(row["acknowledged"]),
        )
