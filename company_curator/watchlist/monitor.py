"""Growth monitor for watchlist companies.

SRP: Only responsible for tracking and evaluating growth metrics.
DIP: Depends on Database and BaseDataFetcher abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from company_curator.data.db import Database
from company_curator.data.fetcher import BaseDataFetcher
from company_curator.watchlist.manager import WatchlistEntry


@dataclass
class GrowthReport:
    ticker: str
    company_name: str
    days_watched: int
    entry_price: float
    current_price: float
    price_change_pct: float
    entry_revenue: float | None
    current_revenue: float | None
    revenue_change_pct: float | None
    meets_price_threshold: bool
    meets_revenue_threshold: bool
    ready_for_investment: bool


class GrowthMonitor:
    """Monitors watchlist companies for sustained growth over 3 months."""

    def __init__(
        self,
        db: Database,
        fetcher: BaseDataFetcher,
        price_threshold_pct: float = 15.0,
        revenue_threshold_pct: float = 10.0,
        monitoring_days: int = 90,
    ) -> None:
        self._db = db
        self._fetcher = fetcher
        self._price_threshold = price_threshold_pct
        self._revenue_threshold = revenue_threshold_pct
        self._monitoring_days = monitoring_days

    def evaluate(self, entry: WatchlistEntry) -> GrowthReport:
        """Evaluate a watchlist entry's growth performance."""
        current_price = self._fetcher.get_current_price(entry.ticker) or entry.entry_price
        metrics = self._fetcher.get_financial_metrics(entry.ticker)
        current_revenue = metrics.revenue_ttm if metrics else None

        added = datetime.fromisoformat(entry.added_date)
        days_watched = (datetime.now() - added).days

        price_change = ((current_price - entry.entry_price) / entry.entry_price) * 100

        revenue_change: float | None = None
        if entry.entry_revenue and current_revenue:
            revenue_change = ((current_revenue - entry.entry_revenue) / entry.entry_revenue) * 100

        meets_price = price_change >= self._price_threshold
        meets_revenue = revenue_change is not None and revenue_change >= self._revenue_threshold
        past_monitoring = days_watched >= self._monitoring_days

        return GrowthReport(
            ticker=entry.ticker,
            company_name=entry.company_name,
            days_watched=days_watched,
            entry_price=entry.entry_price,
            current_price=current_price,
            price_change_pct=price_change,
            entry_revenue=entry.entry_revenue,
            current_revenue=current_revenue,
            revenue_change_pct=revenue_change,
            meets_price_threshold=meets_price,
            meets_revenue_threshold=meets_revenue,
            ready_for_investment=past_monitoring and meets_price and meets_revenue,
        )

    def evaluate_all(self, entries: list[WatchlistEntry]) -> list[GrowthReport]:
        """Evaluate all watchlist entries."""
        return [self.evaluate(entry) for entry in entries]

    def record_daily_price(self, ticker: str) -> None:
        """Record today's closing price for historical tracking."""
        current_price = self._fetcher.get_current_price(ticker)
        if current_price is None:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        self._db.execute(
            """INSERT OR IGNORE INTO price_history (ticker, date, close_price)
               VALUES (?, ?, ?)""",
            (ticker, today, current_price),
        )
        self._db.commit()
