"""Composite candidate source — merges several sources with fallback.

SRP: Only orchestrates other sources (merge, dedup, cap). Holds no sourcing
logic of its own.
OCP: Compose any set of CandidateSources (e.g. YFinanceScreenSource first,
StaticUniverseSource as fallback) without changing this class.
"""

from __future__ import annotations

from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource


class CompositeCandidateSource(CandidateSource):
    """Queries each source in order, merging unique tickers up to `limit`.

    Sources are tried in priority order: the first to return results fills the
    list, and later sources act as fallback. A source that raises or returns
    nothing is skipped, so a dynamic source can degrade to the static universe.
    """

    def __init__(self, sources: list[CandidateSource]) -> None:
        self._sources = sources

    def get_candidates(self, prefs: ResolvedPreferences, limit: int) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []

        for source in self._sources:
            try:
                candidates = source.get_candidates(prefs, limit)
            except Exception:  # noqa: BLE001 — one bad source must not break sourcing
                continue

            for ticker in candidates:
                if ticker not in seen:
                    seen.add(ticker)
                    merged.append(ticker)
                    if len(merged) >= limit:
                        return merged

        return merged
