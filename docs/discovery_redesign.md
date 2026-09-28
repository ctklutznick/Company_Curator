# Discovery Redesign — Real Candidate Sourcing

Status: **done** (approved & implemented 2026-09-28). Replaced the hardcoded
ticker universe with a pluggable, real candidate-sourcing layer.

## 1. Problem

`GrowthScreener.screen()` → `YFinanceDataFetcher.get_top_gainers()` iterates a
hardcoded ~90-ticker string (`_get_screening_universe`), calling `yf.Ticker().info`
on each.

- **Not discovery** — can only surface tickers already on the list.
- **Wrong layering (SRP)** — "where candidates come from" is baked into the data
  *fetcher*, which should only fetch data for a ticker you already have.
- **Slow/fragile** — ~180 `.info` calls per user per run, no cross-user caching.

## 2. Goal / non-goals

- **Goal:** a pluggable candidate-sourcing layer pulling a broad, fresh universe
  from real sources, feeding the existing screen → score → analyze pipeline
  unchanged downstream.
- **Non-goals (this phase):** scorer, analysis reports, watchlist. Fundamental
  filtering (`_passes_filters`) stays put.

## 3. Architecture

New abstraction, separate from both fetcher and screener:

```
discovery/
├── sources/
│   ├── base.py            # CandidateSource ABC   ← new seam
│   ├── static.py          # StaticUniverseSource  (today's list, fallback)
│   ├── yfinance_screen.py # YFinanceScreenSource  (real, dynamic) ← v1 default
│   └── composite.py       # CompositeCandidateSource (merge + dedup)
├── screener.py            # GrowthScreener takes a CandidateSource
└── ...
```

```python
class CandidateSource(ABC):
    @abstractmethod
    def get_candidates(self, prefs: ResolvedPreferences, limit: int) -> list[str]:
        """Return validated candidate tickers. Never raises — degrades to []."""
```

- **SRP:** sourcing ≠ fetching ≠ screening.
- **OCP/LSP:** new sources subclass `CandidateSource`; `CompositeCandidateSource`
  merges a list of them — add sources without touching the screener.
- **DIP:** `GrowthScreener(fetcher, source, ...)`; composition roots
  (`scheduler.py`, `main.py`) wire the concrete source.
- **Cleanup:** remove `get_top_gainers` + `_get_screening_universe` from
  `YFinanceDataFetcher` (not on the `BaseDataFetcher` ABC, so nothing else breaks).
  The static list moves into `StaticUniverseSource`.

`screen()` becomes: `tickers = source.get_candidates(prefs, count*2)` → same
per-ticker fetch + `_passes_filters` loop as today.

## 4. v1 data source — `YFinanceScreenSource`

yfinance 1.2.0 provides both:
- **Predefined screens:** `day_gainers`, `most_actives`, `small_cap_gainers`,
  `aggressive_small_caps`, `growth_technology_stocks`, `undervalued_growth_stocks`,
  `undervalued_large_caps`.
- **Custom `EquityQuery`** — server-side filters (region, market cap, sector, price).

Map preferences → query: aggressive → `small_cap_gainers`/`aggressive_small_caps`;
conservative → `undervalued_large_caps`; sector prefs → `EquityQuery` sector filter.
No new dependency, no API key, no scraping-ToS risk.

⚠️ **Version pin:** `requirements.txt` currently pins `yfinance>=0.2.36`, but
`yf.screen` didn't exist then. Bump to `yfinance>=1.2.0` or the new source crashes
in CI/Fly.

## 5. Security & robustness

Scraped/queried tickers are untrusted external input:
- **Validate every symbol** before it touches `yf.Ticker` or SQL:
  `^[A-Z][A-Z0-9.\-]{0,9}$`; drop the rest (`is_valid_ticker`, unit-tested).
- **Fail safe:** any source error → `[]`; `CompositeCandidateSource` falls through
  to the next source, ultimately `StaticUniverseSource`, so a run never dies on a
  source hiccup.
- **Timeouts + caching** on network calls; cap candidate count to bound work/cost.
- Prefer the yfinance path over HTML scraping to respect data-source ToS.

## 6. Efficiency — daily candidate cache

Staggered multi-user runs would each re-query the same universe. Cache per day
(a `candidate_universe` table keyed by date + query signature, or an in-process
TTL cache) so the universe is fetched ~once/day, not once/user.

## 7. TDD plan (tests first)

| Unit | Test-first cases |
|---|---|
| `is_valid_ticker` | accepts AAPL/BRK.B; rejects injection, empty, over-long |
| `StaticUniverseSource` | deterministic list, respects `limit` |
| `YFinanceScreenSource` | mock `yf.screen`/`EquityQuery`: risk→query mapping, validate+dedup, `[]` on exception |
| `CompositeCandidateSource` | merge, dedup preserving order, skip failing source |
| `GrowthScreener` | fake `CandidateSource` (no network) still applies `_passes_filters` |

No live network in tests — sources mocked, matching the `conftest` mock-fetcher pattern.

## 8. Ordered to-do checklist

1. [x] Bump `yfinance>=1.2.0`; suite green (isolated commit).
2. [x] `is_valid_ticker`/`clean_tickers` helper + tests.
3. [x] `CandidateSource` ABC + `StaticUniverseSource` (moved the list) + tests.
4. [x] `YFinanceScreenSource` (risk-profile→screen mapping) + mocked tests.
5. [x] `CompositeCandidateSource` + tests.
6. [x] Refactored `GrowthScreener` to take a `CandidateSource`; deleted
   `get_top_gainers`/`_get_screening_universe`; updated `scheduler.py` wiring + tests.
7. [x] Shared `TTLCache` for screen results + tests.
8. [x] Updated `CLAUDE.md` discovery flow; committed/pushed.

## Follow-ups (not in v1)

- Sector-aware `EquityQuery` (use `prefs.sectors` to filter the screen).
- Consider a real data provider (FMP/Finnhub) if yfinance proves too flaky.
- DB-backed candidate cache if the in-process cache proves insufficient across restarts.

## Decisions

- **v1 source:** yfinance screen + static fallback (no third-party API, no HTML scraping).
