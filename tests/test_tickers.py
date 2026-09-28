"""Tests for ticker validation/normalization used to sanitize sourced symbols."""

from company_curator.utils.tickers import clean_tickers, is_valid_ticker


def test_is_valid_ticker_accepts_real_symbols():
    assert is_valid_ticker("AAPL")
    assert is_valid_ticker("BRK.B")   # dotted class share
    assert is_valid_ticker("BF-B")    # hyphenated class share
    assert is_valid_ticker("A")       # single letter


def test_is_valid_ticker_is_case_insensitive():
    assert is_valid_ticker("aapl")


def test_is_valid_ticker_rejects_junk():
    assert not is_valid_ticker("")
    assert not is_valid_ticker("123")            # must start with a letter
    assert not is_valid_ticker("ABCDEFGHIJK")    # 11 chars, too long
    assert not is_valid_ticker("'; DROP TABLE")  # injection / spaces
    assert not is_valid_ticker(None)             # type: ignore[arg-type]


def test_clean_tickers_normalizes_dedups_and_filters():
    result = clean_tickers(["aapl", "AAPL", "123", "MSFT", "'; DROP", "  nvda  "])
    assert result == ["AAPL", "MSFT", "NVDA"]  # uppercased, deduped, order preserved


def test_clean_tickers_handles_non_strings():
    assert clean_tickers(["AAPL", None, 42, "MSFT"]) == ["AAPL", "MSFT"]
