"""Peer Comparison Table analysis module.

SRP: Generates only the Peer Comparison report section.
DIP: Depends on injected Anthropic client and data fetcher.
"""

from __future__ import annotations

import anthropic

from company_curator.analysis.prompts import peer_comparison_prompt
from company_curator.data.fetcher import BaseDataFetcher


class PeerComparisonAnalyzer:
    """Generates relative valuation comparison using real data + Claude analysis."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        fetcher: BaseDataFetcher,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self._client = client
        self._fetcher = fetcher
        self._model = model

    def analyze(self, ticker: str, competitor1: str, competitor2: str) -> str:
        """Generate a Peer Comparison report with real financial data."""
        # Fetch real metrics for all three companies
        data_context = self._build_data_context(ticker, competitor1, competitor2)
        prompt = peer_comparison_prompt(ticker, competitor1, competitor2)

        full_prompt = (
            f"Here is current financial data to use in your analysis:\n\n"
            f"{data_context}\n\n{prompt}"
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            messages=[{"role": "user", "content": full_prompt}],
        )

        return response.content[0].text

    def _build_data_context(self, *tickers: str) -> str:
        lines: list[str] = []
        for t in tickers:
            metrics = self._fetcher.get_financial_metrics(t)
            if metrics:
                ps = f"{metrics.ps_ratio_ttm:.2f}" if metrics.ps_ratio_ttm else "N/A"
                ev = f"{metrics.ev_ebitda:.2f}" if metrics.ev_ebitda else "N/A"
                gm = f"{metrics.gross_margin:.1%}" if metrics.gross_margin else "N/A"
                rg = f"{metrics.revenue_growth_yoy:.1%}" if metrics.revenue_growth_yoy else "N/A"
                lines.append(f"{t}: P/S(TTM)={ps}, EV/EBITDA={ev}, Gross Margin={gm}, Rev Growth={rg}")
            else:
                lines.append(f"{t}: Data unavailable")
        return "\n".join(lines)
