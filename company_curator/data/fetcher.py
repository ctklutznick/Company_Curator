"""Financial data fetcher using yfinance.

SRP: Sole responsibility is retrieving market data from yfinance.
ISP: Provides focused methods for specific data needs rather than one giant fetch.
DIP: Consumers depend on the DataFetcher abstraction.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

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


@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    published: str


class BaseDataFetcher(ABC):
    """Abstract base for data fetching — allows swapping data sources (OCP/DIP)."""

    @abstractmethod
    def get_company_info(self, ticker: str) -> CompanyInfo | None:
        ...

    @abstractmethod
    def get_financial_metrics(self, ticker: str) -> FinancialMetrics | None:
        ...

    @abstractmethod
    def get_price_history(
        self, ticker: str, period: str = "3mo", start: str | None = None
    ) -> list[PriceData]:
        ...

    @abstractmethod
    def get_current_price(self, ticker: str) -> float | None:
        ...

    def get_current_prices(self, tickers: list[str]) -> dict[str, float | None]:
        """Fetch current prices for many tickers. Default: sequential."""
        return {t: self.get_current_price(t) for t in tickers}

    @abstractmethod
    def get_news(self, ticker: str, count: int = 5) -> list[NewsItem]:
        ...


class YFinanceDataFetcher(BaseDataFetcher):
    """Fetches financial data from Yahoo Finance via yfinance."""

    _PRICE_TTL = 120  # seconds a cached live price stays fresh

    def __init__(self) -> None:
        self._price_cache: dict[str, tuple[float, float]] = {}
        self._price_lock = Lock()

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

    def get_price_history(
        self, ticker: str, period: str = "3mo", start: str | None = None
    ) -> list[PriceData]:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start) if start else stock.history(period=period)
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
        now = time.time()
        with self._price_lock:
            cached = self._price_cache.get(ticker)
            if cached and now - cached[1] < self._PRICE_TTL:
                return cached[0]

        price = self._fetch_current_price(ticker)
        if price is not None:
            with self._price_lock:
                self._price_cache[ticker] = (price, now)
        return price

    def _fetch_current_price(self, ticker: str) -> float | None:
        """Fetch the latest price using the lightweight fast_info endpoint.

        `fast_info` avoids the heavy `.info` payload; fall back to the last
        close from a 1-day history if it's unavailable.
        """
        try:
            price = getattr(yf.Ticker(ticker).fast_info, "last_price", None)
            if price:
                return float(price)
        except Exception:
            pass
        try:
            hist = yf.Ticker(ticker).history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
        return None

    def get_current_prices(self, tickers: list[str]) -> dict[str, float | None]:
        """Fetch many current prices in parallel (cache-aware per ticker)."""
        if not tickers:
            return {}
        results: dict[str, float | None] = {}
        with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as ex:
            futures = {ex.submit(self.get_current_price, t): t for t in tickers}
            for fut in futures:
                ticker = futures[fut]
                try:
                    results[ticker] = fut.result()
                except Exception:
                    results[ticker] = None
        return results

    def get_news(self, ticker: str, count: int = 5) -> list[NewsItem]:
        try:
            stock = yf.Ticker(ticker)
            raw_news = stock.news or []
            items: list[NewsItem] = []
            for item in raw_news[:count]:
                content = item.get("content", {})
                title = content.get("title", "")
                if not title:
                    continue
                summary = content.get("summary", "")
                provider = content.get("provider", {})
                source = provider.get("displayName", "Unknown")
                published = content.get("pubDate", "")
                items.append(NewsItem(
                    title=title,
                    summary=summary[:300] if summary else "",
                    source=source,
                    published=published,
                ))
            return items
        except Exception:
            return []

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
