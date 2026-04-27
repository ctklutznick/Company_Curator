"""AI chat route — answer questions about stocks.

SRP: Only handles the AI Q&A endpoint.
DIP: Uses injected Anthropic client and data fetcher.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

ai_chat_bp = Blueprint("ai_chat", __name__)


@ai_chat_bp.route("/ask", methods=["POST"])
def ask():
    """Answer a question about a stock using Claude."""
    data = request.get_json()
    ticker = data.get("ticker", "").upper()
    question = data.get("question", "").strip()

    if not ticker or not question:
        return jsonify({"error": "Missing ticker or question"}), 400

    client = current_app.config["APP_CLIENT"]
    fetcher = current_app.config["APP_FETCHER"]

    # Build context from live data
    info = fetcher.get_company_info(ticker)
    metrics = fetcher.get_financial_metrics(ticker)

    context_parts = [f"Stock: {ticker}"]
    if info:
        context_parts.append(f"Company: {info.name}")
        context_parts.append(f"Sector: {info.sector}, Industry: {info.industry}")
        context_parts.append(f"Price: ${info.current_price:.2f}, Market Cap: ${info.market_cap/1e9:.1f}B")
    if metrics:
        if metrics.revenue_growth_yoy:
            context_parts.append(f"YoY Revenue Growth: {metrics.revenue_growth_yoy:.1%}")
        if metrics.gross_margin:
            context_parts.append(f"Gross Margin: {metrics.gross_margin:.1%}")
        if metrics.ps_ratio_ttm:
            context_parts.append(f"P/S (TTM): {metrics.ps_ratio_ttm:.1f}x")
        if metrics.ev_ebitda:
            context_parts.append(f"EV/EBITDA: {metrics.ev_ebitda:.1f}x")

    context = "\n".join(context_parts)

    prompt = (
        f"You are a concise investment research assistant. Answer the user's question "
        f"about {ticker} using the live data provided. Keep your answer to 2-4 sentences. "
        f"Be direct and analytical.\n\n"
        f"=== LIVE DATA ===\n{context}\n=== END DATA ===\n\n"
        f"Question: {question}"
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.content[0].text
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
