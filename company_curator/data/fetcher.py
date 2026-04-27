"""Financial data fetcher using yfinance.

SRP: Sole responsibility is retrieving market data from yfinance.
ISP: Provides focused methods for specific data needs rather than one giant fetch.
DIP: Consumers depend on the DataFetcher abstraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import yfinance as yf


@dataclass
class CompanyInfo:
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: float
    current_price: float
    description: str


@dataclass
class FinancialMetrics:
    ticker: str
    ps_ratio_ttm: float | None
    ps_ratio_forward: float | None
    ev_ebitda: float | None
    gross_margin: float | None
    revenue_growth_yoy: float | None
    revenue_ttm: float | None


@dataclass
class PriceData:
    ticker: str
    date: datetime
    close: float
    volume: int


class BaseDataFetcher(ABC):
    """Abstract base for data fetching — allows swapping data sources (OCP/DIP)."""

    @abstractmethod
    def get_company_info(self, ticker: str) -> CompanyInfo | None:
        ...

    @abstractmethod
    def get_financial_metrics(self, ticker: str) -> FinancialMetrics | None:
        ...

    @abstractmethod
    def get_price_history(self, ticker: str, period: str = "3mo") -> list[PriceData]:
        ...

    @abstractmethod
    def get_current_price(self, ticker: str) -> float | None:
        ...


class YFinanceDataFetcher(BaseDataFetcher):
    """Fetches financial data from Yahoo Finance via yfinance."""

    def get_company_info(self, ticker: str) -> CompanyInfo | None:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return CompanyInfo(
                ticker=ticker,
                name=info.get("longName", ticker),
                sector=info.get("sector", "Unknown"),
                industry=info.get("industry", "Unknown"),
                market_cap=info.get("marketCap", 0),
                current_price=info.get("currentPrice", info.get("regularMarketPrice", 0)),
                description=info.get("longBusinessSummary", ""),
            )
        except Exception:
            return None

    def get_financial_metrics(self, ticker: str) -> FinancialMetrics | None:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return FinancialMetrics(
                ticker=ticker,
                ps_ratio_ttm=info.get("priceToSalesTrailing12Months"),
                ps_ratio_forward=info.get("forwardPE"),  # Approximation
                ev_ebitda=info.get("enterpriseToEbitda"),
                gross_margin=info.get("grossMargins"),
                revenue_growth_yoy=info.get("revenueGrowth"),
                revenue_ttm=info.get("totalRevenue"),
            )
        except Exception:
            return None

    def get_price_history(self, ticker: str, period: str = "3mo") -> list[PriceData]:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            return [
                PriceData(
                    ticker=ticker,
                    date=index.to_pydatetime(),
                    close=row["Close"],
                    volume=int(row["Volume"]),
                )
                for index, row in hist.iterrows()
            ]
        except Exception:
            return []

    def get_current_price(self, ticker: str) -> float | None:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return info.get("currentPrice", info.get("regularMarketPrice"))
        except Exception:
            return None

    def get_top_gainers(self, count: int = 50) -> list[str]:
        """Get tickers with strong recent momentum for screening."""
        try:
            # Screen using S&P 500 + growth stocks as the universe
            sp500 = yf.Tickers(self._get_screening_universe())
            results: list[tuple[str, float]] = []

            for ticker_str in self._get_screening_universe().split():
                try:
                    stock = yf.Ticker(ticker_str)
                    info = stock.info
                    growth = info.get("revenueGrowth", 0) or 0
                    market_cap = info.get("marketCap", 0) or 0
                    if market_cap > 500_000_000 and growth > 0.1:
                        results.append((ticker_str, growth))
                except Exception:
                    continue

            results.sort(key=lambda x: x[1], reverse=True)
            return [t[0] for t in results[:count]]
        except Exception:
            return []

    @staticmethod
    def _get_screening_universe() -> str:
        """Return a curated list of tickers to screen from.

        In production, this could be expanded to pull from multiple indices.
        """
        return (
            "AAPL MSFT GOOGL AMZN NVDA META TSLA AMD AVGO ORCL "
            "CRM ADBE NOW SNOW PLTR NET DDOG CRWD ZS MDB "
            "PANW FTNT BILL HUBS SHOP MELI SE SQ COIN RBLX "
            "ABNB UBER LYFT DASH DUOL CELH ONON DECK LULU ELF "
            "AXON TOST TTD ROKU PINS SNAP SMCI ARM IONQ RGTI "
            "AFRM SOFI HOOD UPST OPEN CAVA TOST MNDY CFLT S "
            "GTLB APP IOT BRZE DOCN DT PATH ESTC PCOR "
            "GLBE PAYC DKNG FOUR BROS VERX ALKT ZI CLBT GENI "
            "ANET WDAY TEAM VEEV TWLO OKTA U RIVN LCID JOBY "
            "LUNR ASTS AEHR ENPH SEDG FSLR RUN ARRY CHPT BLNK"
        )
