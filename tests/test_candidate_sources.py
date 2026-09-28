"""Tests for the candidate-sourcing layer."""

import pytest

from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource
from company_curator.discovery.sources.composite import CompositeCandidateSource
from company_curator.discovery.sources.static import StaticUniverseSource
from company_curator.discovery.sources.yfinance_screen import YFinanceScreenSource


def _prefs(risk="moderate"):
    return ResolvedPreferences(
        risk_profile=risk,
        sectors=None,
        avoid=None,
        daily_picks=3,
        min_market_cap=2_000_000_000,
        min_revenue_growth=0.10,
    )


def test_static_source_is_a_candidate_source():
    assert isinstance(StaticUniverseSource(), CandidateSource)


def test_static_source_returns_valid_tickers_and_respects_limit():
    source = StaticUniverseSource()
    result = source.get_candidates(_prefs(), limit=5)
    assert len(result) == 5
    assert all(t.isupper() for t in result)
    assert len(set(result)) == 5  # no dupes


def test_static_source_is_deterministic():
    source = StaticUniverseSource()
    assert source.get_candidates(_prefs(), limit=10) == source.get_candidates(_prefs(), limit=10)


def test_static_source_accepts_custom_universe_and_sanitizes_it():
    # 123 (no leading letter) and @bad (illegal char) are format-invalid and dropped.
    source = StaticUniverseSource(universe="aapl msft 123 @bad")
    assert source.get_candidates(_prefs(), limit=10) == ["AAPL", "MSFT"]


def test_candidate_source_is_abstract():
    with pytest.raises(TypeError):
        CandidateSource()  # type: ignore[abstract]


# --- YFinanceScreenSource (screen fn injected so tests never hit the network) ---


_UNSET = object()


class _FakeScreen:
    def __init__(self, result=_UNSET, raises=False):
        self.calls = []
        self._result = {"quotes": []} if result is _UNSET else result
        self._raises = raises

    def __call__(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if self._raises:
            raise RuntimeError("screen unavailable")
        return self._result


def test_yf_source_is_a_candidate_source():
    assert isinstance(YFinanceScreenSource(screen_fn=_FakeScreen()), CandidateSource)


def test_yf_source_maps_risk_profile_to_screen():
    fake = _FakeScreen()
    source = YFinanceScreenSource(screen_fn=fake)

    source.get_candidates(_prefs("aggressive"), 10)
    source.get_candidates(_prefs("conservative"), 10)
    source.get_candidates(_prefs("moderate"), 10)

    assert fake.calls[0][0] == "small_cap_gainers"
    assert fake.calls[1][0] == "undervalued_large_caps"
    assert fake.calls[2][0] == "growth_technology_stocks"


def test_yf_source_unknown_risk_falls_back_to_default_screen():
    fake = _FakeScreen()
    YFinanceScreenSource(screen_fn=fake).get_candidates(_prefs("wild"), 10)
    assert fake.calls[0][0] == YFinanceScreenSource.DEFAULT_SCREEN


def test_yf_source_extracts_validates_and_dedups_symbols():
    fake = _FakeScreen(result={"quotes": [
        {"symbol": "aapl"}, {"symbol": "AAPL"}, {"symbol": "123"},
        {"symbol": "MSFT"}, {"no_symbol": 1}, {"symbol": "@bad"},
    ]})
    source = YFinanceScreenSource(screen_fn=fake)
    assert source.get_candidates(_prefs(), 10) == ["AAPL", "MSFT"]


def test_yf_source_respects_limit():
    fake = _FakeScreen(result={"quotes": [{"symbol": s} for s in ("AAA", "BBB", "CCC", "DDD")]})
    source = YFinanceScreenSource(screen_fn=fake)
    assert source.get_candidates(_prefs(), limit=2) == ["AAA", "BBB"]


def test_yf_source_returns_empty_on_error():
    source = YFinanceScreenSource(screen_fn=_FakeScreen(raises=True))
    assert source.get_candidates(_prefs(), 10) == []


def test_yf_source_handles_malformed_result():
    assert YFinanceScreenSource(screen_fn=_FakeScreen(result={"oops": 1})).get_candidates(_prefs(), 10) == []
    assert YFinanceScreenSource(screen_fn=_FakeScreen(result=None)).get_candidates(_prefs(), 10) == []


# --- CompositeCandidateSource -------------------------------------------------


class _FixedSource(CandidateSource):
    def __init__(self, tickers, raises=False):
        self._tickers = tickers
        self._raises = raises

    def get_candidates(self, prefs, limit):
        if self._raises:
            raise RuntimeError("source down")
        return list(self._tickers[:limit])


def test_composite_is_a_candidate_source():
    assert isinstance(CompositeCandidateSource([]), CandidateSource)


def test_composite_merges_and_dedups_preserving_order():
    composite = CompositeCandidateSource([
        _FixedSource(["AAPL", "MSFT"]),
        _FixedSource(["MSFT", "NVDA"]),
    ])
    assert composite.get_candidates(_prefs(), 10) == ["AAPL", "MSFT", "NVDA"]


def test_composite_falls_through_to_next_source_when_first_is_empty():
    composite = CompositeCandidateSource([
        _FixedSource([]),
        _FixedSource(["AAPL", "MSFT"]),
    ])
    assert composite.get_candidates(_prefs(), 10) == ["AAPL", "MSFT"]


def test_composite_skips_a_failing_source():
    composite = CompositeCandidateSource([
        _FixedSource([], raises=True),
        _FixedSource(["AAPL"]),
    ])
    assert composite.get_candidates(_prefs(), 10) == ["AAPL"]


def test_composite_respects_limit_and_stops_early():
    composite = CompositeCandidateSource([
        _FixedSource(["AAPL", "MSFT", "NVDA"]),
        _FixedSource(["TSLA"]),
    ])
    assert composite.get_candidates(_prefs(), limit=2) == ["AAPL", "MSFT"]


def test_composite_returns_empty_when_all_sources_empty():
    composite = CompositeCandidateSource([_FixedSource([]), _FixedSource([])])
    assert composite.get_candidates(_prefs(), 10) == []
