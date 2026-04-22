"""Deep Dive analysis module.

SRP: Generates only the Deep Dive report section.
DIP: Depends on injected Anthropic client and data fetcher.
"""

import anthropic

from company_curator.analysis.prompts import deep_dive_prompt
from company_curator.data.fetcher import BaseDataFetcher


class DeepDiveAnalyzer:
    """Generates the 4-part Deep Dive report using Claude, grounded in live data."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        fetcher: BaseDataFetcher,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self._client = client
        self._fetcher = fetcher
        self._model = model

    def analyze(self, ticker: str) -> str:
        """Generate a Deep Dive report for the given ticker."""
        context = self._build_context(ticker)
        prompt = deep_dive_prompt(ticker, context)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def _build_context(self, ticker: str) -> str:
        """Fetch live data from yfinance and format it for the prompt."""
        lines: list[str] = []

        info = self._fetcher.get_company_info(ticker)
        if info:
            lines.append(f"Company: {info.name}")
            lines.append(f"Sector: {info.sector} | Industry: {info.industry}")
            lines.append(f"Market Cap: ${info.market_cap:,.0f}")
            lines.append(f"Current Price: ${info.current_price:.2f}")
            lines.append(f"Description: {info.description}")

        metrics = self._fetcher.get_financial_metrics(ticker)
        if metrics:
            lines.append(f"P/S (TTM): {metrics.ps_ratio_ttm}")
            lines.append(f"EV/EBITDA: {metrics.ev_ebitda}")
            lines.append(f"Gross Margin: {metrics.gross_margin:.1%}" if metrics.gross_margin else "Gross Margin: N/A")
            lines.append(f"Revenue Growth YoY: {metrics.revenue_growth_yoy:.1%}" if metrics.revenue_growth_yoy else "Revenue Growth YoY: N/A")
            lines.append(f"Revenue (TTM): ${metrics.revenue_ttm:,.0f}" if metrics.revenue_ttm else "Revenue (TTM): N/A")

        prices = self._fetcher.get_price_history(ticker, period="6mo")
        if prices:
            first, last = prices[0], prices[-1]
            change_pct = ((last.close - first.close) / first.close) * 100
            lines.append(f"6-Month Price Change: {change_pct:+.1f}% (${first.close:.2f} → ${last.close:.2f})")

        return "\n".join(lines) if lines else "No live data available."
