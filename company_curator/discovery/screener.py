"""Market screener for finding candidate companies.

SRP: Only responsible for screening the market for candidates.
OCP: Screening strategies can be extended via the BaseScreener abstraction.
DIP: Depends on BaseDataFetcher abstraction, not YFinance directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from company_curator.data.fetcher import BaseDataFetcher, CompanyInfo, FinancialMetrics


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
    """Screens for high-growth companies with strong fundamentals."""

    def __init__(self, fetcher: BaseDataFetcher) -> None:
        self._fetcher = fetcher

    def screen(self, count: int = 20) -> list[ScreenerResult]:
        """Screen the market for high-growth candidates."""
        candidates = self._fetcher.get_top_gainers(count=count * 2)
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
        """Apply basic quantitative filters before qualitative scoring."""
        if info.market_cap < 500_000_000:
            return False
        if metrics.revenue_growth_yoy is not None and metrics.revenue_growth_yoy < 0.05:
            return False
        return True
