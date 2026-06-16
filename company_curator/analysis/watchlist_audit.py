"""Monthly watchlist audit analyzer.

SRP: Only responsible for generating the monthly audit analysis via Claude.
DIP: Depends on injected Anthropic client and data fetcher.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

from company_curator.analysis.prompts import monthly_audit_prompt
from company_curator.data.fetcher import BaseDataFetcher


@dataclass
class AuditedStock:
    ticker: str
    company_name: str
    score: float
    recommendation: str
    reasoning: str
    current_price: float
    entry_price: float
    price_change_pct: float
    rank: int | None = None


@dataclass
class AuditResult:
    top_picks: list[AuditedStock] = field(default_factory=list)
    holds: list[AuditedStock] = field(default_factory=list)
    drops: list[AuditedStock] = field(default_factory=list)
    summary: str = ""


class WatchlistAuditor:
    """Evaluates all watchlist stocks in a single Claude call for relative comparison."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        fetcher: BaseDataFetcher,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._client = client
        self._fetcher = fetcher
        self._model = model

    def audit(self, entries: list) -> AuditResult:
        """Run a monthly audit on all watchlist entries.

        Args:
            entries: list of watchlist entry objects with ticker, company_name, entry_price.
        """
        if not entries:
            return AuditResult(summary="No stocks on watchlist to audit.")

        stocks_data = self._build_stocks_data(entries)
        prompt = monthly_audit_prompt(stocks_data)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_response(response.content[0].text, entries)

    def _build_stocks_data(self, entries: list) -> str:
        sections: list[str] = []

        for entry in entries:
            ticker = entry.ticker
            lines = [f"\n--- {ticker} ({entry.company_name}) ---"]
            lines.append(f"Entry Price: ${entry.entry_price:.2f}")

            info = self._fetcher.get_company_info(ticker)
            if info:
                lines.append(f"Current Price: ${info.current_price:.2f}")
                lines.append(f"Market Cap: ${info.market_cap:,.0f}")
                lines.append(f"Sector: {info.sector} | Industry: {info.industry}")

            metrics = self._fetcher.get_financial_metrics(ticker)
            if metrics:
                if metrics.revenue_growth_yoy:
                    lines.append(f"Revenue Growth YoY: {metrics.revenue_growth_yoy:.1%}")
                if metrics.gross_margin:
                    lines.append(f"Gross Margin: {metrics.gross_margin:.1%}")
                if metrics.ps_ratio_ttm:
                    lines.append(f"P/S (TTM): {metrics.ps_ratio_ttm:.1f}")
                if metrics.ev_ebitda:
                    lines.append(f"EV/EBITDA: {metrics.ev_ebitda:.1f}")
                if metrics.revenue_ttm:
                    lines.append(f"Revenue (TTM): ${metrics.revenue_ttm:,.0f}")

            prices = self._fetcher.get_price_history(ticker, period="6mo")
            if prices:
                first, last = prices[0], prices[-1]
                change = ((last.close - first.close) / first.close) * 100
                lines.append(f"6-Month Price Change: {change:+.1f}%")

            entry_change = 0.0
            current = self._fetcher.get_current_price(ticker)
            if current:
                entry_change = ((current - entry.entry_price) / entry.entry_price) * 100
                lines.append(f"Change Since Entry: {entry_change:+.1f}%")

            sections.append("\n".join(lines))

        return "\n".join(sections)

    def _parse_response(self, text: str, entries: list) -> AuditResult:
        try:
            json_str = text
            if "```" in text:
                json_str = text.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            data = json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            return AuditResult(summary="Failed to parse audit response.")

        entry_map = {e.ticker: e for e in entries}
        result = AuditResult(summary=data.get("summary", ""))

        for pick in data.get("top_picks", []):
            stock = self._build_audited_stock(pick, entry_map, "top_pick")
            if stock:
                result.top_picks.append(stock)

        for hold in data.get("holds", []):
            stock = self._build_audited_stock(hold, entry_map, "hold")
            if stock:
                result.holds.append(stock)

        for drop in data.get("drops", []):
            stock = self._build_audited_stock(drop, entry_map, "drop")
            if stock:
                result.drops.append(stock)

        return result

    def _build_audited_stock(
        self, item: dict, entry_map: dict, recommendation: str
    ) -> AuditedStock | None:
        ticker = item.get("ticker", "").upper()
        entry = entry_map.get(ticker)
        if not entry:
            return None

        current = self._fetcher.get_current_price(ticker) or entry.entry_price
        change_pct = ((current - entry.entry_price) / entry.entry_price) * 100

        return AuditedStock(
            ticker=ticker,
            company_name=entry.company_name,
            score=float(item.get("score", 0)),
            recommendation=recommendation,
            reasoning=item.get("reasoning", ""),
            current_price=current,
            entry_price=entry.entry_price,
            price_change_pct=change_pct,
            rank=item.get("rank"),
        )
