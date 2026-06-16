"""Dashboard route — home page showing watchlist overview.

SRP: Only handles the dashboard route and view logic.
"""

from __future__ import annotations

from collections import OrderedDict

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from company_curator.data.fetcher import BaseDataFetcher
from company_curator.watchlist.manager import WatchlistManager
from company_curator.watchlist.price_tracker import PriceTracker

dashboard_bp = Blueprint("dashboard", __name__)

_VALID_PERIODS = ("1mo", "3mo", "6mo", "ytd", "1y")


def _portfolio_series(fetcher: BaseDataFetcher, tickers: list[str], period: str) -> list[dict]:
    """Sum one share of each watchlist ticker into a single value-over-time line.

    Forward-fills each ticker's last known close so a missing day for one stock
    doesn't make the combined line dip.
    """
    per_ticker: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()
    for ticker in tickers:
        closes = {
            p.date.strftime("%Y-%m-%d"): p.close
            for p in fetcher.get_price_history(ticker, period=period)
        }
        if closes:
            per_ticker[ticker] = closes
            all_dates.update(closes)

    if not per_ticker:
        return []

    last_known: dict[str, float | None] = {t: None for t in per_ticker}
    points: list[dict] = []
    for date in sorted(all_dates):
        total = 0.0
        have_any = False
        for ticker, closes in per_ticker.items():
            if date in closes:
                last_known[ticker] = closes[date]
            if last_known[ticker] is not None:
                total += last_known[ticker]
                have_any = True
        if have_any:
            points.append({"date": date, "value": round(total, 2)})
    return points


@dashboard_bp.route("/")
@login_required
def index():
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    user_id = current_user.id

    manager = WatchlistManager(db, user_id)
    tracker = PriceTracker(db, fetcher, user_id)

    entries = manager.list_active()
    watchlist_data: list[dict] = []
    total_entry_value = 0.0
    total_current_value = 0.0

    for entry in entries:
        # Use live price for accurate delta, fall back to last recorded close
        live_price = fetcher.get_current_price(entry.ticker)
        if live_price is None:
            latest = tracker.get_latest(entry.ticker)
            live_price = latest.close_price if latest else entry.entry_price

        change_pct = ((live_price - entry.entry_price) / entry.entry_price) * 100
        change_dollar = live_price - entry.entry_price

        total_entry_value += entry.entry_price
        total_current_value += live_price

        watchlist_data.append({
            "ticker": entry.ticker,
            "name": entry.company_name,
            "entry_price": entry.entry_price,
            "current_price": live_price,
            "change_pct": change_pct,
            "change_dollar": change_dollar,
            "added_date": entry.added_date[:10],
        })

    # Aggregate portfolio stats
    aggregate = {
        "total_entry": total_entry_value,
        "total_current": total_current_value,
        "total_change_dollar": total_current_value - total_entry_value,
        "total_change_pct": (
            ((total_current_value - total_entry_value) / total_entry_value) * 100
            if total_entry_value > 0 else 0.0
        ),
        "count": len(watchlist_data),
    }

    # Fetch picks grouped by date (last 30 days worth)
    all_picks = db.fetchall(
        "SELECT * FROM daily_picks WHERE user_id = ? ORDER BY date DESC LIMIT 30",
        (user_id,),
    )

    # Group by date, preserving order
    picks_by_date: OrderedDict[str, list] = OrderedDict()
    for pick in all_picks:
        date = pick["date"]
        if date not in picks_by_date:
            picks_by_date[date] = []
        picks_by_date[date].append(pick)

    # Which date tab is active? Default to most recent
    active_date = request.args.get("date")
    dates = list(picks_by_date.keys())
    if active_date not in picks_by_date and dates:
        active_date = dates[0]

    pending_drops = db.fetchone(
        """SELECT COUNT(*) as cnt FROM monthly_audit_entries
           WHERE user_id = ? AND recommendation = 'drop' AND drop_acknowledged = 0""",
        (user_id,),
    )
    pending_drop_count = pending_drops["cnt"] if pending_drops else 0

    latest_audit_month = None
    if pending_drop_count > 0:
        latest = db.fetchone(
            "SELECT audit_month FROM monthly_audits WHERE user_id = ? ORDER BY audit_month DESC LIMIT 1",
            (user_id,),
        )
        if latest:
            latest_audit_month = latest["audit_month"]

    return render_template(
        "dashboard.html",
        watchlist=watchlist_data,
        aggregate=aggregate,
        picks_by_date=picks_by_date,
        active_date=active_date,
        dates=dates,
        pending_drop_count=pending_drop_count,
        latest_audit_month=latest_audit_month,
    )


@dashboard_bp.route("/portfolio-history")
@login_required
def portfolio_history():
    """Combined value-over-time of the active watchlist, for the dashboard chart."""
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    user_id = current_user.id

    period = request.args.get("period", "6mo")
    if period not in _VALID_PERIODS:
        period = "6mo"

    entries = WatchlistManager(db, user_id).list_active()
    points = _portfolio_series(fetcher, [e.ticker for e in entries], period)
    return jsonify({"period": period, "points": points})
