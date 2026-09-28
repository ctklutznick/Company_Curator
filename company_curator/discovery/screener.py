"""Market screener for finding candidate companies.

SRP: Given candidates from a CandidateSource, apply quantitative filters.
OCP: Screening strategies extend BaseScreener; candidate sources are swappable.
DIP: Depends on BaseDataFetcher and CandidateSource abstractions, not concretions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from company_curator.data.fetcher import BaseDataFetcher, CompanyInfo, FinancialMetrics
from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource


@dataclass
class ScreenerResult:
    info: CompanyInfo
    metrics: FinancialMetrics


class BaseScreener(ABC):
    """Abstract screener — new strategies extend this (OCP)."""

    @abstractmethod
    def screen(self, count: int) -> list[ScreenerResult]:
        ...


class GrowthScreener(BaseScreener):
    """Screens candidate companies for growth + fundamentals thresholds."""

    def __init__(
        self,
        fetcher: BaseDataFetcher,
        source: CandidateSource,
        prefs: ResolvedPreferences,
    ) -> None:
        self._fetcher = fetcher
        self._source = source
        self._prefs = prefs

    def screen(self, count: int = 20) -> list[ScreenerResult]:
        """Pull candidates from the source and keep those passing the filters."""
        candidates = self._source.get_candidates(self._prefs, limit=count * 2)
        results: list[ScreenerResult] = []

        for ticker in candidates:
            info = self._fetcher.get_company_info(ticker)
            if info is None:
                continue

            metrics = self._fetcher.get_financial_metrics(ticker)
            if metrics is None:
                continue

            if self._passes_filters(info, metrics):
                results.append(ScreenerResult(info=info, metrics=metrics))

            if len(results) >= count:
                break

        return results

    def _passes_filters(self, info: CompanyInfo, metrics: FinancialMetrics) -> bool:
        """Apply quantitative filters before qualitative scoring."""
        if info.market_cap < self._prefs.min_market_cap:
            return False
        if (
            metrics.revenue_growth_yoy is not None
            and metrics.revenue_growth_yoy < self._prefs.min_revenue_growth
        ):
            return False
        return True
