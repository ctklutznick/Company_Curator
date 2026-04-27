"""Report routes — view deep dive analysis for daily picks.

SRP: Only handles report viewing routes.
"""

from __future__ import annotations

from flask import Blueprint, current_app, render_template, abort

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/<date>/<ticker>")
def detail(date: str, ticker: str):
    """Show the full deep dive report for a pick."""
    ticker = ticker.upper()
    db = current_app.config["APP_DB"]

    pick = db.fetchone(
        "SELECT * FROM daily_picks WHERE date = ? AND ticker = ?",
        (date, ticker),
    )
    if not pick:
        abort(404)

    return render_template(
        "report_detail.html",
        pick=pick,
    )
