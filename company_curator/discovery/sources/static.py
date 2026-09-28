"""Static, curated ticker universe.

This is the original hardcoded list, now behind the CandidateSource interface.
It serves as a deterministic fallback when dynamic sources are unavailable, and
as a stable universe for tests.
"""

from __future__ import annotations

from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource
from company_curator.utils.tickers import clean_tickers

# Curated growth-stock universe. Kept as a fallback; dynamic sources
# (YFinanceScreenSource) are preferred for real discovery.
DEFAULT_UNIVERSE = (
    "AAPL MSFT GOOGL AMZN NVDA META TSLA AMD AVGO ORCL "
    "CRM ADBE NOW SNOW PLTR NET DDOG CRWD ZS MDB "
    "PANW FTNT BILL HUBS SHOP MELI SE SQ COIN RBLX "
    "ABNB UBER LYFT DASH DUOL CELH ONON DECK LULU ELF "
    "AXON TOST TTD ROKU PINS SNAP SMCI ARM IONQ RGTI "
    "AFRM SOFI HOOD UPST OPEN CAVA MNDY CFLT S "
    "GTLB APP IOT BRZE DOCN DT PATH ESTC PCOR "
    "GLBE PAYC DKNG FOUR BROS VERX ALKT ZI CLBT GENI "
    "ANET WDAY TEAM VEEV TWLO OKTA U RIVN LCID JOBY "
    "LUNR ASTS AEHR ENPH SEDG FSLR RUN ARRY CHPT BLNK"
)


class StaticUniverseSource(CandidateSource):
    """Returns tickers from a fixed, curated list. Ignores preferences."""

    def __init__(self, universe: str | None = None) -> None:
        self._tickers = clean_tickers((universe or DEFAULT_UNIVERSE).split())

    def get_candidates(self, prefs: ResolvedPreferences, limit: int) -> list[str]:
        return self._tickers[:limit]
