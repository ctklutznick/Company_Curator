"""Daily price tracking for watchlist stocks.

SRP: Only responsible for recording and retrieving OHLCV price data.
DIP: Depends on Database and BaseDataFetcher abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from company_curator.data.db import Database
from company_curator.data.fetcher import BaseDataFetcher


@dataclass
class DailyPrice:
    ticker: str
    date: str
    open_price: float | None
    close_price: float | None
    high_price: float | None
    low_price: float | None
    volume: int | None


class PriceTracker:
    """Records and retrieves daily OHLCV data for watchlist stocks."""

    def __init__(self, db: Database, fetcher: BaseDataFetcher) -> None:
        self._db = db
        self._fetcher = fetcher

    def record_daily_prices(self, tickers: list[str]) -> list[DailyPrice]:
        """Fetch today's OHLCV data for all tickers and store it."""
        recorded: list[DailyPrice] = []
        for ticker in tickers:
            price = self._fetch_and_store(ticker)
            if price:
                recorded.append(price)
        return recorded

    def get_history(self, ticker: str, days: int = 90) -> list[DailyPrice]:
        """Get recorded price history for a ticker, most recent first."""
        rows = self._db.fetchall(
            """SELECT * FROM daily_prices
               WHERE ticker = ?
               ORDER BY date DESC
               LIMIT ?""",
            (ticker.upper(), days),
        )
        return [self._row_to_price(r) for r in rows]

    def get_latest(self, ticker: str) -> DailyPrice | None:
        """Get the most recent recorded price for a ticker."""
        row = self._db.fetchone(
            """SELECT * FROM daily_prices
               WHERE ticker = ?
               ORDER BY date DESC
               LIMIT 1""",
            (ticker.upper(),),
        )
        return self._row_to_price(row) if row else None

    def _fetch_and_store(self, ticker: str) -> DailyPrice | None:
        """Fetch today's price data from yfinance and write to daily_prices."""
        try:
            prices = self._fetcher.get_price_history(ticker, period="5d")
            if not prices:
                return None

            latest = prices[-1]
            today = latest.date.strftime("%Y-%m-%d")

            # yfinance PriceData only has close/volume, get OHLC from raw history
            import yfinance as yf
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty:
                return None

            last_row = hist.iloc[-1]
            daily = DailyPrice(
                ticker=ticker,
                date=today,
                open_price=float(last_row["Open"]),
                close_price=float(last_row["Close"]),
                high_price=float(last_row["High"]),
                low_price=float(last_row["Low"]),
                volume=int(last_row["Volume"]),
            )

            self._db.execute(
                """INSERT OR REPLACE INTO daily_prices
                   (ticker, date, open_price, close_price, high_price, low_price, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (daily.ticker, daily.date, daily.open_price, daily.close_price,
                 daily.high_price, daily.low_price, daily.volume),
            )
            self._db.commit()
            return daily
        except Exception:
            return None

    @staticmethod
    def _row_to_price(row) -> DailyPrice:
        return DailyPrice(
            ticker=row["ticker"],
            date=row["date"],
            open_price=row["open_price"],
            close_price=row["close_price"],
            high_price=row["high_price"],
            low_price=row["low_price"],
            volume=row["volume"],
        )
