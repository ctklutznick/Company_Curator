"""CandidateSource abstraction.

SRP: A candidate source's only job is to produce candidate ticker symbols.
It does NOT fetch fundamentals (that's BaseDataFetcher) or filter them
(that's the screener).
OCP/LSP: New sources subclass this; any source is substitutable for another.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from company_curator.discovery.preferences import ResolvedPreferences


class CandidateSource(ABC):
    """Produces a list of candidate tickers to feed the screener."""

    @abstractmethod
    def get_candidates(self, prefs: ResolvedPreferences, limit: int) -> list[str]:
        """Return up to `limit` validated, de-duplicated candidate tickers.

        Implementations must never raise on external failure — degrade to an
        empty list so the daily pipeline survives a source outage.
        """
        ...
