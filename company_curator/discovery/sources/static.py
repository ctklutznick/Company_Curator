"""Static, curated ticker universe.

This is the original hardcoded list, now behind the CandidateSource interface.
It serves as a deterministic fallback when dynamic sources are unavailable, and
as a stable universe for tests.
"""

from __future__ import annotations

from company_curator.discovery.preferences import ResolvedPreferences
from company_curator.discovery.sources.base import CandidateSource
from company_curator.utils.tickers import clean_tickers

# Curated growth-stock universe (~200 names). Kept as a fallback; the dynamic
# YFinanceScreenSource is preferred for real discovery. Duplicates are harmless
# (clean_tickers de-dups). Grouped loosely by theme for maintainability.
DEFAULT_UNIVERSE = (
    # Mega-cap tech / platforms
    "AAPL MSFT GOOGL GOOG AMZN NVDA META NFLX TSLA ORCL CRM ADBE INTU "
    # Semiconductors & equipment
    "AVGO AMD QCOM TXN MU INTC AMAT LRCX KLAC ADI MRVL MCHP NXPI ON ASML TSM "
    "MPWR TER ENTG SMCI ARM CRDO ALAB "
    # Software / SaaS
    "NOW SNOW PLTR NET DDOG CRWD ZS MDB PANW FTNT BILL HUBS DOCN DT PATH ESTC "
    "PCOR MNDY CFLT GTLB APP IOT BRZE TEAM WDAY VEEV TWLO OKTA ADSK CDNS SNPS "
    "ANSS FICO MSCI ROP FTV DOCU ZM FROG AI BASE AMPL ASAN PD FSLY S ZI CLBT "
    # Fintech / payments
    "SQ AFRM SOFI HOOD UPST COIN PYPL V MA FIS GPN FI NU MQ DLO PAGS STNE FOUR "
    "TOST GLBE PAYC VERX ALKT "
    # Consumer / internet / retail
    "SHOP MELI SE ABNB UBER LYFT DASH DUOL RBLX ETSY W CHWY BKNG EXPE MAR PINS "
    "SNAP ROKU TTD SPOT RDDT TTWO EA BABA PDD JD BIDU "
    # Consumer brands / restaurants
    "CELH ONON DECK LULU ELF CROX BOOT CMG WING TXRH DPZ BROS CAVA DKNG GENI "
    # Healthcare / biotech
    "LLY NVO ISRG DXCM PODD VRTX REGN MRNA BNTX CRSP NTLA BEAM RXRX HIMS DOCS TEM "
    # Industrials / power / space / clean energy / EV
    "AXON GEV VRT PWR ETN NEE ENPH SEDG FSLR RUN ARRY CHPT BLNK RIVN LCID JOBY "
    "LUNR ASTS RKLB ACHR KTOS AEHR IONQ RGTI"
)


class StaticUniverseSource(CandidateSource):
    """Returns tickers from a fixed, curated list. Ignores preferences."""

    def __init__(self, universe: str | None = None) -> None:
        self._tickers = clean_tickers((universe or DEFAULT_UNIVERSE).split())

    def get_candidates(self, prefs: ResolvedPreferences, limit: int) -> list[str]:
        return self._tickers[:limit]
