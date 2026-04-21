"""Deep Dive analysis module.

SRP: Generates only the Deep Dive report section.
DIP: Depends on injected Anthropic client.
"""

import anthropic

from company_curator.analysis.prompts import deep_dive_prompt


class DeepDiveAnalyzer:
    """Generates the 4-part Deep Dive report using Claude."""

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-4-20250514") -> None:
        self._client = client
        self._model = model

    def analyze(self, ticker: str) -> str:
        """Generate a Deep Dive report for the given ticker."""
        prompt = deep_dive_prompt(ticker)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
