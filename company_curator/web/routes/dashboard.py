"""Dashboard route — home page showing watchlist overview.

SRP: Only handles the dashboard route and view logic.
"""

from __future__ import annotations

from collections import OrderedDict

from flask import Blueprint, current_app, render_template, request
from flask_login import current_user, login_required

from company_curator.watchlist.manager import WatchlistManager
from company_curator.watchlist.price_tracker import PriceTracker

dashboard_bp = Blueprint("dashboard", __name__)


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
