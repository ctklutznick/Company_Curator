"""Tests for GrowthScreener now that it sources candidates via a CandidateSource."""

from company_curator.data.fetcher import BaseDataFetcher, CompanyInfo, FinancialMetrics
from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.screener import GrowthScreener
from company_curator.discovery.sources.base import CandidateSource


def _prefs(min_market_cap=1_000_000_000, min_revenue_growth=0.10):
    return ResolvedPreferences(
        risk_profile="moderate",
        sectors=None,
        avoid=None,
        daily_picks=3,
        min_market_cap=min_market_cap,
        min_revenue_growth=min_revenue_growth,
    )


def _info(ticker, market_cap):
    return CompanyInfo(
        ticker=ticker, name=f"{ticker} Inc", sector="Tech", industry="Software",
        market_cap=market_cap, current_price=10.0, description="",
    )


def _metrics(ticker, growth):
    return FinancialMetrics(
        ticker=ticker, ps_ratio_ttm=None, ps_ratio_forward=None, ev_ebitda=None,
        gross_margin=None, revenue_growth_yoy=growth, revenue_ttm=None,
    )


class _FakeFetcher(BaseDataFetcher):
    def __init__(self, infos, metrics):
        self._infos = infos
        self._metrics = metrics

    def get_company_info(self, ticker):
        return self._infos.get(ticker)

    def get_financial_metrics(self, ticker):
        return self._metrics.get(ticker)

    def get_price_history(self, ticker, period="3mo", start=None):
        return []

    def get_current_price(self, ticker):
        return None

    def get_news(self, ticker, count=5):
        return []


class _ListSource(CandidateSource):
    def __init__(self, tickers):
        self._tickers = tickers

    def get_candidates(self, prefs, limit):
        return self._tickers[:limit]


class _SpySource(CandidateSource):
    """Records the limit it was asked for."""

    def __init__(self):
        self.asked_limit = None

    def get_candidates(self, prefs, limit):
        self.asked_limit = limit
        return []


def test_screener_draws_the_configured_candidate_pool_from_source():
    spy = _SpySource()
    screener = GrowthScreener(_FakeFetcher({}, {}), spy, _prefs(), candidate_pool=200)
    screener.screen(count=30)
    assert spy.asked_limit == 200


def test_screener_keeps_companies_meeting_thresholds():
    infos = {"AAPL": _info("AAPL", 2_000_000_000)}
    metrics = {"AAPL": _metrics("AAPL", 0.20)}
    screener = GrowthScreener(_FakeFetcher(infos, metrics), _ListSource(["AAPL"]), _prefs())
    results = screener.screen(count=5)
    assert [r.info.ticker for r in results] == ["AAPL"]


def test_screener_filters_out_small_market_cap():
    infos = {"TINY": _info("TINY", 500_000_000)}
    metrics = {"TINY": _metrics("TINY", 0.50)}
    screener = GrowthScreener(_FakeFetcher(infos, metrics), _ListSource(["TINY"]), _prefs())
    assert screener.screen(count=5) == []


def test_screener_filters_out_low_revenue_growth():
    infos = {"SLOW": _info("SLOW", 2_000_000_000)}
    metrics = {"SLOW": _metrics("SLOW", 0.05)}
    screener = GrowthScreener(_FakeFetcher(infos, metrics), _ListSource(["SLOW"]), _prefs())
    assert screener.screen(count=5) == []


def test_screener_skips_tickers_missing_data():
    infos = {"AAPL": _info("AAPL", 2_000_000_000)}  # MSFT has no info
    metrics = {"AAPL": _metrics("AAPL", 0.20)}       # MSFT has no metrics
    screener = GrowthScreener(_FakeFetcher(infos, metrics), _ListSource(["MSFT", "AAPL"]), _prefs())
    assert [r.info.ticker for r in screener.screen(count=5)] == ["AAPL"]


def test_screener_respects_count():
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    infos = {t: _info(t, 2_000_000_000) for t in tickers}
    metrics = {t: _metrics(t, 0.20) for t in tickers}
    screener = GrowthScreener(_FakeFetcher(infos, metrics), _ListSource(tickers), _prefs())
    assert len(screener.screen(count=2)) == 2
