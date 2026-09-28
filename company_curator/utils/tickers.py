"""Ticker symbol validation and normalization.

SRP: Only responsible for validating/cleaning ticker symbols. Candidate sources
pull symbols from external, untrusted places (screeners, APIs); everything must
pass through here before it reaches yfinance or SQL.
"""

from __future__ import annotations

import re
from typing import Iterable

# A leading letter followed by up to 9 letters/digits/dots/hyphens.
# Covers ordinary tickers plus class shares like BRK.B and BF-B.
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def is_valid_ticker(symbol: object) -> bool:
    """Return True if `symbol` looks like a real ticker (case-insensitive)."""
    if not isinstance(symbol, str):
        return False
    return bool(_TICKER_RE.match(symbol.strip().upper()))


def clean_tickers(symbols: Iterable[object]) -> list[str]:
    """Uppercase, validate, and de-duplicate `symbols`, preserving first-seen order.

    Non-strings and invalid symbols are dropped. This is the single choke point
    for sanitizing externally sourced candidate tickers.
    """
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in symbols:
        if not isinstance(raw, str):
            continue
        ticker = raw.strip().upper()
        if is_valid_ticker(ticker) and ticker not in seen:
            seen.add(ticker)
            cleaned.append(ticker)
    return cleaned
