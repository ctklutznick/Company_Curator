"""Short Report (skeptic risk assessment) module.

SRP: Generates only the Short Report section.
DIP: Depends on injected Anthropic client.
"""

import anthropic

from company_curator.analysis.prompts import short_report_prompt


class ShortReportAnalyzer:
    """Generates the skeptic risk assessment using Claude."""

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-4-20250514") -> None:
        self._client = client
        self._model = model

    def analyze(self, ticker: str) -> str:
        """Generate a Short Report (risk assessment) for the given ticker."""
        prompt = short_report_prompt(ticker)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
