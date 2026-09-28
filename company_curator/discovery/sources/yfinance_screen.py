"""Dynamic candidate source backed by Yahoo Finance's screener (yf.screen).

Maps a user's risk profile to a predefined Yahoo screen so discovery surfaces a
real, refreshed universe instead of a fixed list.

Robustness: yf.screen hits Yahoo's unofficial, undocumented endpoints, which can
break, rate-limit, or change shape. This source therefore never raises — it
degrades to an empty list so a CompositeCandidateSource can fall back to the
static universe and the daily pipeline survives.
"""

from __future__ import annotations

import time
from typing import Callable

import yfinance as yf

from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource
from company_curator.utils.tickers import clean_tickers

# Yahoo caps a single screen response at 250.
_MAX_SIZE = 250

# How long a screen result stays fresh. Long enough that a single daily,
# staggered multi-user run reuses one call per screen (cutting rate-limit
# exposure), short enough that the next day's run refetches.
_DEFAULT_TTL_SECONDS = 6 * 3600


class TTLCache:
    """Minimal time-to-live cache keyed by screen name. Clock injected for tests."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.time) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._store: dict[str, tuple[float, list[str]]] = {}

    def get(self, key: str) -> list[str] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self._clock() - stored_at > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: list[str]) -> None:
        self._store[key] = (self._clock(), value)


# Process-wide cache the scheduler injects so all users in one daily batch share
# screen results. Tests use their own (or a per-instance) cache for isolation.
SHARED_SCREEN_CACHE = TTLCache(_DEFAULT_TTL_SECONDS)


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

    def __init__(
        self,
        screen_fn: Callable[..., object] = yf.screen,
        cache: TTLCache | None = None,
    ) -> None:
        # Injected for testability (DIP) — tests pass a fake so no network is hit.
        self._screen = screen_fn
        # Default to a fresh per-instance cache; the scheduler injects the
        # process-wide SHARED_SCREEN_CACHE to reuse results across users.
        self._cache = cache if cache is not None else TTLCache(_DEFAULT_TTL_SECONDS)

    def get_candidates(self, prefs: ResolvedPreferences, limit: int) -> list[str]:
        screen_name = self.RISK_SCREENS.get(prefs.risk_profile, self.DEFAULT_SCREEN)

        cached = self._cache.get(screen_name)
        if cached is not None:
            return cached[:limit]

        tickers = self._fetch(screen_name, limit)
        if tickers:  # never cache an empty/failed result — retry next time
            self._cache.set(screen_name, tickers)
        return tickers[:limit]

    def _fetch(self, screen_name: str, limit: int) -> list[str]:
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
        return clean_tickers(symbols)
