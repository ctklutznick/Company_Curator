"""Prompt templates for company analysis.

SRP: This module only defines prompt templates — no execution logic.
OCP: New prompts can be added without modifying existing ones.
"""


def deep_dive_prompt(ticker: str) -> str:
    return (
        f"Generate a comprehensive Deep Research Report on {ticker}. "
        "Cover these 4 areas: "
        "1. Business Model: How exactly do they make money? Core product in plain English. "
        "2. Moat and Competition: Top 3 competitors. Does {ticker} have a unique technological "
        "advantage or patent that competitors lack? "
        "3. Catalyst: Upcoming product launches, regulatory approvals, or partnerships "
        "in the next 12 months? "
        "4. Asymmetry Check: Low valuation floor vs high growth ceiling? Why or why not?"
    ).format(ticker=ticker)


def peer_comparison_prompt(ticker: str, competitor1: str, competitor2: str) -> str:
    return (
        f"Create a relative valuation table for {ticker} vs "
        f"{competitor1} and {competitor2}. "
        "Include: P/S (TTM and forward), EV/EBITDA, gross margin, "
        "YoY revenue growth, and a Value/Growth Score "
        "(P/S TTM / revenue growth %). Lower score = more growth per "
        "valuation dollar. "
        "Format as a clean markdown table. Include a brief analysis "
        "of which company offers the best value-to-growth ratio."
    )


def short_report_prompt(ticker: str) -> str:
    return (
        f"Act as a skeptic. Write a 3-point risk assessment for {ticker} "
        "focusing on: accounting irregularities, customer concentration, "
        "and competitive threats. "
        "For each point, rate the risk as LOW, MEDIUM, or HIGH and explain why. "
        "End with an overall risk verdict."
    )


def discovery_scoring_prompt(tickers_with_data: str) -> str:
    return (
        "You are an investment research analyst focused on finding high-growth companies "
        "with strong qualitative factors. Analyze the following companies and select the "
        "top 3 based on:\n\n"
        "1. Growth potential (revenue growth, market expansion)\n"
        "2. Company culture and management quality\n"
        "3. Market sentiment and momentum\n"
        "4. Competitive moat strength\n"
        "5. Catalyst potential (upcoming events that could drive growth)\n\n"
        "For each of your top 3 picks, provide:\n"
        "- Ticker\n"
        "- Company name\n"
        "- Score (1-100)\n"
        "- One paragraph reasoning covering the qualitative factors\n\n"
        "Respond in this exact JSON format:\n"
        '[\n'
        '  {"ticker": "XXX", "name": "Company Name", "score": 85, '
        '"reasoning": "..."}\n'
        ']\n\n'
        f"Companies to evaluate:\n{tickers_with_data}"
    )
