"""Movement notes generator — explains why stocks moved.

SRP: Only responsible for generating price movement explanations.
DIP: Depends on injected Anthropic client and data fetcher.
"""

from __future__ import annotations

import anthropic

from company_curator.analysis.prompts import movement_notes_prompt
from company_curator.data.db import Database
from company_curator.data.fetcher import BaseDataFetcher
from company_curator.watchlist.price_tracker import DailyPrice


class MovementNotesGenerator:
    """Generates Claude-powered explanations for stock price movements."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        fetcher: BaseDataFetcher,
        db: Database,
        model: str = "claude-sonnet-4-20250514",
        threshold_pct: float = 2.0,
    ) -> None:
        self._client = client
        self._fetcher = fetcher
        self._db = db
        self._model = model
        self._threshold = threshold_pct

    def generate_daily_notes(self, tickers: list[str]) -> list[dict[str, str]]:
        """Generate movement notes for tickers that moved beyond the threshold."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        notes: list[dict[str, str]] = []

        for ticker in tickers:
            prices = self._fetcher.get_price_history(ticker, period="5d")
            if len(prices) < 2:
                continue

            prev_close = prices[-2].close
            curr_close = prices[-1].close
            change_pct = ((curr_close - prev_close) / prev_close) * 100

            if abs(change_pct) < self._threshold:
                continue

            price_data = self._format_price_data(prices)
            note = self._generate_note(ticker, "daily", price_data, change_pct)

            self._store_note(ticker, today, "daily", change_pct, note)
            notes.append({"ticker": ticker, "note": note, "change_pct": change_pct})

        return notes

    def generate_weekly_notes(self, tickers: list[str]) -> list[dict[str, str]]:
        """Generate weekly summary notes."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        notes: list[dict[str, str]] = []

        for ticker in tickers:
            prices = self._fetcher.get_price_history(ticker, period="1mo")
            if len(prices) < 5:
                continue

            week_prices = prices[-5:]
            change_pct = ((week_prices[-1].close - week_prices[0].close) / week_prices[0].close) * 100

            price_data = self._format_price_data(week_prices)
            note = self._generate_note(ticker, "weekly", price_data, change_pct)

            self._store_note(ticker, today, "weekly", change_pct, note)
            notes.append({"ticker": ticker, "note": note, "change_pct": change_pct})

        return notes

    def generate_monthly_notes(self, tickers: list[str]) -> list[dict[str, str]]:
        """Generate monthly summary notes."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        notes: list[dict[str, str]] = []

        for ticker in tickers:
            prices = self._fetcher.get_price_history(ticker, period="3mo")
            if len(prices) < 20:
                continue

            month_prices = prices[-22:]
            change_pct = ((month_prices[-1].close - month_prices[0].close) / month_prices[0].close) * 100

            price_data = self._format_price_data(month_prices)
            note = self._generate_note(ticker, "monthly", price_data, change_pct)

            self._store_note(ticker, today, "monthly", change_pct, note)
            notes.append({"ticker": ticker, "note": note, "change_pct": change_pct})

        return notes

    def get_notes(self, ticker: str, limit: int = 30) -> list[dict]:
        """Retrieve stored movement notes for a ticker."""
        rows = self._db.fetchall(
            """SELECT date, period, price_change_pct, note
               FROM movement_notes
               WHERE ticker = ?
               ORDER BY date DESC, period
               LIMIT ?""",
            (ticker.upper(), limit),
        )
        return [
            {
                "date": r["date"],
                "period": r["period"],
                "change_pct": r["price_change_pct"],
                "note": r["note"],
            }
            for r in rows
        ]

    def _generate_note(
        self, ticker: str, period: str, price_data: str, change_pct: float
    ) -> str:
        prompt = movement_notes_prompt(ticker, period, price_data, change_pct)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _store_note(
        self, ticker: str, date: str, period: str, change_pct: float, note: str
    ) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO movement_notes
               (ticker, date, period, price_change_pct, note)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker.upper(), date, period, change_pct, note),
        )
        self._db.commit()

    @staticmethod
    def _format_price_data(prices) -> str:
        lines: list[str] = []
        for p in prices:
            date_str = p.date.strftime("%Y-%m-%d") if hasattr(p.date, "strftime") else str(p.date)
            lines.append(f"{date_str}: Close=${p.close:.2f}, Vol={p.volume:,}")
        return "\n".join(lines)
