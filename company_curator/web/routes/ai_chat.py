"""AI chat route — investment research assistant.

SRP: Only handles the AI Q&A endpoint.
DIP: Uses injected Anthropic client and data fetcher.
"""

from __future__ import annotations

import re

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

ai_chat_bp = Blueprint("ai_chat", __name__)

SYSTEM_PROMPT = (
    "You are Curator AI, a knowledgeable investment research assistant. "
    "You have deep expertise in stocks, markets, companies, industries, and investing. "
    "ALWAYS answer using your full knowledge — you know about company culture, "
    "management teams, board members, competitive dynamics, industry trends, "
    "macro factors, and more. Use live data provided to supplement your knowledge "
    "with current numbers, but never say you 'don't have data' — you are an expert.\n\n"
    "Rules:\n"
    "- 3-5 sentences MAX. Be direct, specific, and confident.\n"
    "- No headers, no bullet lists, no markdown formatting.\n"
    "- Use plain text only.\n"
    "- End with 'Want me to dig into [specific aspect]?' when relevant.\n"
    "- You provide research analysis, not financial advice."
)


def _build_ticker_context(fetcher, ticker: str) -> str:
    """Build rich context for a specific ticker using live data."""
    parts: list[str] = []

    info = fetcher.get_company_info(ticker)
    if info:
        parts.append(f"Company: {info.name} ({ticker})")
        parts.append(f"Sector: {info.sector} | Industry: {info.industry}")
        parts.append(f"Price: ${info.current_price:.2f} | Market Cap: ${info.market_cap/1e9:.1f}B")

    metrics = fetcher.get_financial_metrics(ticker)
    if metrics:
        if metrics.revenue_growth_yoy:
            parts.append(f"YoY Revenue Growth: {metrics.revenue_growth_yoy:.1%}")
        if metrics.gross_margin:
            parts.append(f"Gross Margin: {metrics.gross_margin:.1%}")
        if metrics.ps_ratio_ttm:
            parts.append(f"P/S (TTM): {metrics.ps_ratio_ttm:.1f}x")
        if metrics.ev_ebitda:
            parts.append(f"EV/EBITDA: {metrics.ev_ebitda:.1f}x")
        if metrics.revenue_ttm:
            parts.append(f"Revenue TTM: ${metrics.revenue_ttm/1e9:.2f}B")

    news_items = fetcher.get_news(ticker, count=5)
    if news_items:
        parts.append("\nRecent News:")
        for item in news_items:
            parts.append(f"- {item.title} ({item.source}, {item.published[:10] if item.published else 'recent'})")

    return "\n".join(parts)


@ai_chat_bp.route("/ask", methods=["POST"])
@login_required
def ask():
    """Answer investment questions using Claude with live market data."""
    data = request.get_json()
    ticker = data.get("ticker", "").strip().upper()
    question = data.get("question", "").strip()

    if not question or len(question) > 2000:
        return jsonify({"error": "Question required (max 2000 characters)"}), 400

    client = current_app.config["APP_CLIENT"]
    fetcher = current_app.config["APP_FETCHER"]

    # Build context — if a ticker is provided or mentioned in the question, fetch its data
    context_parts: list[str] = []

    # Check for ticker in the request or extract from question
    tickers_to_fetch: list[str] = []
    if ticker and re.match(r"^[A-Z0-9]{1,10}$", ticker):
        tickers_to_fetch.append(ticker)

    # Also detect tickers mentioned in the question (e.g. "compare AAPL vs MSFT")
    mentioned = re.findall(r"\b([A-Z]{2,5})\b", question)
    for t in mentioned:
        if t not in tickers_to_fetch and t not in ("AI", "CEO", "IPO", "ETF", "GDP", "CPI", "PE", "EV", "YOY", "TTM", "VS"):
            # Verify it's a real ticker (limit to 3 extra lookups)
            if len(tickers_to_fetch) < 4:
                info = fetcher.get_company_info(t)
                if info and info.name != t:
                    tickers_to_fetch.append(t)

    for t in tickers_to_fetch:
        ctx = _build_ticker_context(fetcher, t)
        if ctx:
            context_parts.append(f"=== LIVE DATA: {t} ===\n{ctx}\n=== END {t} ===")

    context = "\n\n".join(context_parts)

    user_message = question
    if context:
        user_message = f"{context}\n\nQuestion: {question}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        answer = response.content[0].text
        return jsonify({"answer": answer})
    except Exception as e:
        current_app.logger.error("AI chat request failed: %s", e)
        return jsonify({"error": "Something went wrong. Please try again."}), 500
