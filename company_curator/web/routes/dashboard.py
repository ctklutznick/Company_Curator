"""Dashboard route — home page showing watchlist overview.

SRP: Only handles the dashboard route and view logic.
"""

from __future__ import annotations

from collections import OrderedDict

from flask import Blueprint, current_app, render_template, request

from company_curator.watchlist.manager import WatchlistManager
from company_curator.watchlist.price_tracker import PriceTracker

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]

    manager = WatchlistManager(db)
    tracker = PriceTracker(db, fetcher)

    entries = manager.list_active()
    watchlist_data: list[dict] = []

    for entry in entries:
        latest = tracker.get_latest(entry.ticker)
        current_price = latest.close_price if latest else entry.entry_price
        change_pct = ((current_price - entry.entry_price) / entry.entry_price) * 100

        watchlist_data.append({
            "ticker": entry.ticker,
            "name": entry.company_name,
            "entry_price": entry.entry_price,
            "current_price": current_price,
            "change_pct": change_pct,
            "added_date": entry.added_date[:10],
        })

    # Fetch picks grouped by date (last 30 days worth)
    all_picks = db.fetchall(
        "SELECT * FROM daily_picks ORDER BY date DESC LIMIT 30"
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

    return render_template(
        "dashboard.html",
        watchlist=watchlist_data,
        picks_by_date=picks_by_date,
        active_date=active_date,
        dates=dates,
    )
