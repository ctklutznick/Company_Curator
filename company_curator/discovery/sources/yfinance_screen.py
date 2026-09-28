"""Dynamic candidate source backed by Yahoo Finance's screener (yf.screen).

Maps a user's risk profile to a predefined Yahoo screen so discovery surfaces a
real, refreshed universe instead of a fixed list.

Robustness: yf.screen hits Yahoo's unofficial, undocumented endpoints, which can
break, rate-limit, or change shape. This source therefore never raises — it
degrades to an empty list so a CompositeCandidateSource can fall back to the
static universe and the daily pipeline survives.
"""

from __future__ import annotations

from typing import Callable

import yfinance as yf

from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource
from company_curator.utils.tickers import clean_tickers

# Yahoo caps a single screen response at 250.
_MAX_SIZE = 250


class YFinanceScreenSource(CandidateSource):
    """Sources candidates from a predefined Yahoo Finance screen by risk profile."""

    # Risk profile -> predefined Yahoo screen. Aggressive leans small/fast;
    # conservative leans large/undervalued.
    RISK_SCREENS: dict[str, str] = {
        "conservative": "undervalued_large_caps",
        "moderate": "growth_technology_stocks",
        "aggressive": "small_cap_gainers",
    }
    DEFAULT_SCREEN = "day_gainers"

    def __init__(self, screen_fn: Callable[..., object] = yf.screen) -> None:
        # Injected for testability (DIP) — tests pass a fake so no network is hit.
        self._screen = screen_fn

    def get_candidates(self, prefs: ResolvedPreferences, limit: int) -> list[str]:
        screen_name = self.RISK_SCREENS.get(prefs.risk_profile, self.DEFAULT_SCREEN)
        size = max(1, min(limit, _MAX_SIZE))
        try:
            result = self._screen(screen_name, size=size)
        except Exception:  # noqa: BLE001 — a source outage must never break the run
            return []

        if not isinstance(result, dict):
            return []
        quotes = result.get("quotes")
        if not isinstance(quotes, list):
            return []

        symbols = [q.get("symbol") for q in quotes if isinstance(q, dict)]
        return clean_tickers(symbols)[:limit]
