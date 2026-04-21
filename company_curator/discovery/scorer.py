"""Claude-powered qualitative scorer for ranking candidates.

SRP: Only responsible for scoring/ranking candidates using Claude.
DIP: Receives an Anthropic client via injection, not hardcoded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from company_curator.analysis.prompts import discovery_scoring_prompt
from company_curator.discovery.screener import ScreenerResult


@dataclass
class ScoredCompany:
    ticker: str
    name: str
    score: float
    reasoning: str


class QualitativeScorer:
    """Uses Claude to rank companies on qualitative factors."""

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-4-20250514") -> None:
        self._client = client
        self._model = model

    def score_candidates(self, candidates: list[ScreenerResult], top_n: int = 3) -> list[ScoredCompany]:
        """Score candidates and return the top N picks."""
        if not candidates:
            return []

        tickers_data = self._format_candidates(candidates)
        prompt = discovery_scoring_prompt(tickers_data)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_response(response.content[0].text, top_n)

    def _format_candidates(self, candidates: list[ScreenerResult]) -> str:
        lines: list[str] = []
        for c in candidates:
            growth = f"{c.metrics.revenue_growth_yoy:.1%}" if c.metrics.revenue_growth_yoy else "N/A"
            margin = f"{c.metrics.gross_margin:.1%}" if c.metrics.gross_margin else "N/A"
            cap = f"${c.info.market_cap / 1e9:.1f}B"
            lines.append(
                f"- {c.info.ticker} ({c.info.name}): "
                f"Sector={c.info.sector}, Market Cap={cap}, "
                f"Revenue Growth={growth}, Gross Margin={margin}, "
                f"Industry={c.info.industry}"
            )
        return "\n".join(lines)

    def _parse_response(self, text: str, top_n: int) -> list[ScoredCompany]:
        """Parse Claude's JSON response into ScoredCompany objects."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = text
            if "```" in text:
                json_str = text.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            picks = json.loads(json_str)
            results = [
                ScoredCompany(
                    ticker=p["ticker"],
                    name=p["name"],
                    score=float(p["score"]),
                    reasoning=p["reasoning"],
                )
                for p in picks[:top_n]
            ]
            return sorted(results, key=lambda x: x.score, reverse=True)
        except (json.JSONDecodeError, KeyError, IndexError):
            return []
