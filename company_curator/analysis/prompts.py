"""Prompt templates for company analysis.

SRP: This module only defines prompt templates — no execution logic.
OCP: New prompts can be added without modifying existing ones.
"""

from datetime import datetime


def _today() -> str:
    return datetime.now().strftime("%B %d, %Y")


def deep_dive_prompt(ticker: str, financial_context: str) -> str:
    return (
        f"Today is {_today()}. You are writing a research report using LIVE market data "
        f"provided below. Base all financial figures on this data — do not use memorized "
        f"or outdated numbers.\n\n"
        f"=== LIVE FINANCIAL DATA FOR {ticker} ===\n"
        f"{financial_context}\n"
        f"=== END DATA ===\n\n"
        f"Write a concise Deep Research Report on {ticker}. Cover these 4 areas:\n"
        f"1. Business Model — How do they make money? Core product in plain English.\n"
        f"2. Moat & Competition — Top 3 competitors. Any unique technological "
        f"advantage or patent that competitors lack?\n"
        f"3. Catalysts — Upcoming product launches, regulatory shifts, or partnerships "
        f"in the next 12 months.\n"
        f"4. Asymmetry — Low valuation floor vs high growth ceiling? Why or why not?\n\n"
        f"Keep the tone analytical and grounded. Use the live data above for all "
        f"financial figures. Do not invent numbers."
    )


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


def short_report_prompt(ticker: str, financial_context: str) -> str:
    return (
        f"Today is {_today()}. Use the LIVE market data below — do not rely on "
        f"memorized or outdated figures.\n\n"
        f"=== LIVE FINANCIAL DATA FOR {ticker} ===\n"
        f"{financial_context}\n"
        f"=== END DATA ===\n\n"
        f"Act as a skeptic. Write a concise 3-point risk assessment for {ticker} "
        f"covering:\n"
        f"1. Accounting irregularities — rate LOW / MEDIUM / HIGH with reasoning.\n"
        f"2. Customer concentration — rate LOW / MEDIUM / HIGH with reasoning.\n"
        f"3. Competitive threats — rate LOW / MEDIUM / HIGH with reasoning.\n\n"
        f"End with an overall risk verdict. Keep it sharp and data-driven."
    )


def discovery_scoring_prompt(tickers_with_data: str) -> str:
    return (
        f"Today is {_today()}. You are an investment research analyst focused on "
        "finding high-growth companies with strong qualitative factors. Analyze the "
        "following companies and select the top 3 based on:\n\n"
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
