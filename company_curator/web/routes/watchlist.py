"""Watchlist routes — add, remove, view stocks.

SRP: Only handles watchlist-related HTTP routes.
DIP: Delegates to WatchlistManager, PriceTracker, MovementNotesGenerator.
"""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from company_curator.analysis.movement_notes import MovementNotesGenerator
from company_curator.watchlist.manager import WatchlistManager
from company_curator.watchlist.price_tracker import PriceTracker

watchlist_bp = Blueprint("watchlist", __name__)


@watchlist_bp.route("/")
def list_all():
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
            "notes": entry.notes,
        })

    return render_template("watchlist.html", watchlist=watchlist_data)


@watchlist_bp.route("/add/<ticker>")
def add_confirm(ticker: str):
    """Show confirmation page before adding to watchlist (safe from link prefetchers)."""
    ticker = ticker.upper()
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]

    manager = WatchlistManager(db)
    if manager.exists(ticker):
        flash(f"{ticker} is already on your watchlist.", "info")
        return redirect(url_for("watchlist.list_all"))

    info = fetcher.get_company_info(ticker)
    if not info:
        flash(f"Could not find data for {ticker}.", "error")
        return redirect(url_for("dashboard.index"))

    metrics = fetcher.get_financial_metrics(ticker)

    return render_template(
        "add_confirm.html",
        ticker=ticker,
        info=info,
        metrics=metrics,
    )


@watchlist_bp.route("/add/<ticker>", methods=["POST"])
def add_stock(ticker: str):
    """Actually add the stock to the watchlist."""
    ticker = ticker.upper()
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]

    manager = WatchlistManager(db)
    if manager.exists(ticker):
        flash(f"{ticker} is already on your watchlist.", "info")
        return redirect(url_for("watchlist.list_all"))

    info = fetcher.get_company_info(ticker)
    if not info:
        flash(f"Could not find data for {ticker}.", "error")
        return redirect(url_for("dashboard.index"))

    metrics = fetcher.get_financial_metrics(ticker)
    notes = request.form.get("notes", "").strip() or None

    manager.add(
        ticker=ticker,
        company_name=info.name,
        entry_price=info.current_price,
        entry_revenue=metrics.revenue_ttm if metrics else None,
        notes=notes,
    )

    # Record initial price
    tracker = PriceTracker(db, fetcher)
    tracker.record_daily_prices([ticker])

    flash(f"Added {ticker} ({info.name}) to your watchlist at ${info.current_price:.2f}.", "success")
    return redirect(url_for("watchlist.detail", ticker=ticker))


@watchlist_bp.route("/<ticker>")
def detail(ticker: str):
    """Stock detail page with price history and movement notes."""
    ticker = ticker.upper()
    db = current_app.config["APP_DB"]
    fetcher = current_app.config["APP_FETCHER"]
    client = current_app.config["APP_CLIENT"]

    manager = WatchlistManager(db)
    entry = manager.get(ticker)
    if not entry:
        flash(f"{ticker} is not on your watchlist.", "error")
        return redirect(url_for("watchlist.list_all"))

    tracker = PriceTracker(db, fetcher)
    price_history = tracker.get_history(ticker, days=90)

    notes_gen = MovementNotesGenerator(client, fetcher, db)
    movement_notes = notes_gen.get_notes(ticker, limit=30)

    # Current price from fetcher for real-time
    current_price = fetcher.get_current_price(ticker) or entry.entry_price
    change_pct = ((current_price - entry.entry_price) / entry.entry_price) * 100

    return render_template(
        "stock_detail.html",
        entry=entry,
        current_price=current_price,
        change_pct=change_pct,
        price_history=price_history,
        movement_notes=movement_notes,
    )


@watchlist_bp.route("/remove/<ticker>", methods=["POST"])
def remove_stock(ticker: str):
    """Remove a stock from the watchlist."""
    ticker = ticker.upper()
    db = current_app.config["APP_DB"]

    manager = WatchlistManager(db)
    if manager.remove(ticker):
        flash(f"Removed {ticker} from your watchlist.", "success")
    else:
        flash(f"{ticker} is not on the active watchlist.", "error")

    return redirect(url_for("watchlist.list_all"))
