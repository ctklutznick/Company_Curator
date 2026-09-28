"""Tests for the candidate-sourcing layer."""

import pytest

from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource
from company_curator.discovery.sources.static import StaticUniverseSource


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
