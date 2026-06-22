"""Watchlist routes — add, remove, view stocks.

SRP: Only handles watchlist-related HTTP routes.
DIP: Delegates to WatchlistManager, PriceTracker, MovementNotesGenerator.
"""

from __future__ import annotations

import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from company_curator.analysis.movement_notes import MovementNotesGenerator
from company_curator.watchlist.manager import WatchlistManager
from company_curator.watchlist.price_tracker import PriceTracker

watchlist_bp = Blueprint("watchlist", __name__)


@watchlist_bp.route("/search", methods=["POST"])
@login_required
def search():
    """Search for a ticker — redirects to detail if on watchlist, otherwise to add page."""
    query = request.form.get("q", "").strip().upper()
    if not query or not re.match(r"^[A-Z0-9]{1,10}$", query):
        flash("Enter a valid ticker symbol (e.g. AAPL).", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    db = current_app.config["APP_DB"]
    manager = WatchlistManager(db, current_user.id)

    if manager.exists(query):
        return redirect(url_for("watchlist.detail", ticker=query))

    return redirect(url_for("watchlist.add_confirm", ticker=query))


@watchlist_bp.route("/")
@login_required
def list_all():
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    user_id = current_user.id

    manager = WatchlistManager(db, user_id)
    tracker = PriceTracker(db, fetcher, user_id)
    entries = manager.list_active()

    watchlist_data: list[dict] = []
    for entry in entries:
        live_price = fetcher.get_current_price(entry.ticker)
        if live_price is None:
            latest = tracker.get_latest(entry.ticker)
            live_price = latest.close_price if latest else entry.entry_price

        change_pct = ((live_price - entry.entry_price) / entry.entry_price) * 100

        watchlist_data.append({
            "ticker": entry.ticker,
            "name": entry.company_name,
            "entry_price": entry.entry_price,
            "current_price": live_price,
            "change_pct": change_pct,
            "added_date": entry.added_date[:10],
            "notes": entry.notes,
        })

    return render_template("watchlist.html", watchlist=watchlist_data)


@watchlist_bp.route("/review/<date>")
@login_required
def review(date: str):
    """Show the day's picks so the user can add some or all in one place."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        flash("Invalid date.", "error")
        return redirect(url_for("dashboard.index"))

    db = current_app.config["APP_DB"]
    user_id = current_user.id

    picks = db.fetchall(
        """SELECT ticker, company_name, score, reasoning FROM daily_picks
           WHERE user_id = ? AND date = ? ORDER BY score DESC""",
        (user_id, date),
    )
    if not picks:
        flash("No picks found for that date.", "info")
        return redirect(url_for("dashboard.index"))

    manager = WatchlistManager(db, user_id)
    on_watchlist = {p["ticker"] for p in picks if manager.exists(p["ticker"])}

    return render_template(
        "review.html",
        date=date,
        picks=picks,
        on_watchlist=on_watchlist,
    )


@watchlist_bp.route("/add-batch", methods=["POST"])
@login_required
def add_batch():
    """Add several picked tickers at once from the review page."""
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    user_id = current_user.id

    manager = WatchlistManager(db, user_id)

    added: list[str] = []
    skipped: list[str] = []
    for raw in request.form.getlist("tickers"):
        ticker = raw.upper().strip()
        if not re.match(r"^[A-Z0-9]{1,10}$", ticker) or manager.exists(ticker):
            skipped.append(ticker)
            continue
        info = fetcher.get_company_info(ticker)
        if not info:
            skipped.append(ticker)
            continue
        metrics = fetcher.get_financial_metrics(ticker)
        manager.add(
            ticker=ticker,
            company_name=info.name,
            entry_price=info.current_price,
            entry_revenue=metrics.revenue_ttm if metrics else None,
        )
        added.append(ticker)

    if added:
        PriceTracker(db, fetcher, user_id).record_daily_prices(added)
        msg = f"Added {len(added)} to your watchlist: {', '.join(added)}."
        if skipped:
            msg += f" Skipped {len(skipped)} (already added or not found)."
        flash(msg, "success")
    else:
        flash("Nothing added — those tickers were already on your watchlist or could not be found.", "info")

    return redirect(url_for("watchlist.list_all"))


@watchlist_bp.route("/add/<ticker>")
@login_required
def add_confirm(ticker: str):
    """Show confirmation page before adding to watchlist (safe from link prefetchers)."""
    ticker = ticker.upper()
    if not re.match(r"^[A-Z0-9]{1,10}$", ticker):
        flash("Invalid ticker symbol.", "error")
        return redirect(url_for("dashboard.index"))

    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    user_id = current_user.id

    manager = WatchlistManager(db, user_id)
    if manager.exists(ticker):
        flash(f"{ticker} is already on your watchlist.", "info")
        return redirect(url_for("watchlist.list_all"))

    info = fetcher.get_company_info(ticker)
    if not info:
        flash(f"Could not find data for {ticker}.", "error")
        return redirect(url_for("dashboard.index"))

    metrics = fetcher.get_financial_metrics(ticker)

    # Period changes (1M, 6M, YTD) to match stock detail view
    current_price = info.current_price
    period_changes: dict[str, float | None] = {}
    for label, period in [("1mo", "1mo"), ("6mo", "6mo"), ("ytd", "ytd")]:
        prices = fetcher.get_price_history(ticker, period=period)
        if prices and len(prices) >= 2:
            old_close = prices[0].close
            period_changes[label] = ((current_price - old_close) / old_close) * 100
        else:
            period_changes[label] = None

    return render_template(
        "add_confirm.html",
        ticker=ticker,
        info=info,
        metrics=metrics,
        period_changes=period_changes,
    )


@watchlist_bp.route("/add/<ticker>", methods=["POST"])
@login_required
def add_stock(ticker: str):
    """Actually add the stock to the watchlist."""
    ticker = ticker.upper()
    if not re.match(r"^[A-Z0-9]{1,10}$", ticker):
        flash("Invalid ticker symbol.", "error")
        return redirect(url_for("dashboard.index"))

    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    user_id = current_user.id

    manager = WatchlistManager(db, user_id)
    if manager.exists(ticker):
        flash(f"{ticker} is already on your watchlist.", "info")
        return redirect(url_for("watchlist.list_all"))

    info = fetcher.get_company_info(ticker)
    if not info:
        flash(f"Could not find data for {ticker}.", "error")
        return redirect(url_for("dashboard.index"))

    metrics = fetcher.get_financial_metrics(ticker)
    notes = request.form.get("notes", "").strip()[:1000] or None

    manager.add(
        ticker=ticker,
        company_name=info.name,
        entry_price=info.current_price,
        entry_revenue=metrics.revenue_ttm if metrics else None,
        notes=notes,
    )

    # Record initial price
    tracker = PriceTracker(db, fetcher, user_id)
    tracker.record_daily_prices([ticker])

    flash(f"Added {ticker} ({info.name}) to your watchlist at ${info.current_price:.2f}.", "success")
    return redirect(url_for("watchlist.detail", ticker=ticker))


@watchlist_bp.route("/<ticker>")
@login_required
def detail(ticker: str):
    """Stock detail page with price history and movement notes."""
    ticker = ticker.upper()
    if not re.match(r"^[A-Z0-9]{1,10}$", ticker):
        flash("Invalid ticker symbol.", "error")
        return redirect(url_for("watchlist.list_all"))

    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    client = current_app.config["APP_CLIENT"]
    user_id = current_user.id

    manager = WatchlistManager(db, user_id)
    entry = manager.get(ticker)
    if not entry:
        flash(f"{ticker} is not on your watchlist.", "error")
        return redirect(url_for("watchlist.list_all"))

    tracker = PriceTracker(db, fetcher, user_id)
    price_history = tracker.get_history(ticker, days=90)

    notes_gen = MovementNotesGenerator(client, fetcher, db, user_id)
    movement_notes = notes_gen.get_notes(ticker, limit=30)

    # Current price from fetcher for real-time
    current_price = fetcher.get_current_price(ticker) or entry.entry_price
    change_pct = ((current_price - entry.entry_price) / entry.entry_price) * 100

    # Company info and financial metrics
    info = fetcher.get_company_info(ticker)
    metrics = fetcher.get_financial_metrics(ticker)

    # Period changes (1M, 6M, 1Y)
    period_changes = {}
    for label, period in [("1mo", "1mo"), ("6mo", "6mo"), ("ytd", "ytd")]:
        prices = fetcher.get_price_history(ticker, period=period)
        if prices and len(prices) >= 2:
            old_close = prices[0].close
            period_changes[label] = ((current_price - old_close) / old_close) * 100
        else:
            period_changes[label] = None

    latest_report = db.fetchone(
        "SELECT date FROM daily_picks WHERE user_id = ? AND ticker = ? ORDER BY date DESC LIMIT 1",
        (user_id, ticker),
    )

    return render_template(
        "stock_detail.html",
        entry=entry,
        current_price=current_price,
        change_pct=change_pct,
        price_history=price_history,
        movement_notes=movement_notes,
        info=info,
        metrics=metrics,
        period_changes=period_changes,
        latest_report=latest_report,
    )


@watchlist_bp.route("/remove/<ticker>", methods=["POST"])
@login_required
def remove_stock(ticker: str):
    """Remove a stock from the watchlist."""
    ticker = ticker.upper()
    db = current_app.config["APP_DB"]
    user_id = current_user.id

    manager = WatchlistManager(db, user_id)
    if manager.remove(ticker):
        flash(f"Removed {ticker} from your watchlist.", "success")
    else:
        flash(f"{ticker} is not on the active watchlist.", "error")

    return redirect(url_for("watchlist.list_all"))
