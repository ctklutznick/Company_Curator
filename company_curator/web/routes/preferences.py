"""Onboarding questionnaire routes — capture per-user discovery preferences.

SRP: Only handles viewing and saving the preferences questionnaire.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from company_curator.discovery.preferences import (
    VALID_RISK_PROFILES,
    PreferencesManager,
)

preferences_bp = Blueprint("preferences", __name__)

# A small fixed set keeps the questionnaire friendly and the data clean.
SECTOR_CHOICES = (
    "Technology",
    "Healthcare",
    "Financials",
    "Consumer",
    "Energy",
    "Industrials",
    "Communication Services",
    "Real Estate",
)


@preferences_bp.route("/", methods=["GET", "POST"])
@login_required
def edit():
    db = current_app.config["APP_DB"]
    manager = PreferencesManager(db)

    if request.method == "POST":
        risk_profile = request.form.get("risk_profile", "moderate").strip().lower()
        selected_sectors = request.form.getlist("sectors")
        sectors = ",".join(s for s in selected_sectors if s in SECTOR_CHOICES)
        avoid = request.form.get("avoid", "").strip()[:500]

        daily_picks_raw = request.form.get("daily_picks", "").strip()
        try:
            daily_picks = max(1, min(5, int(daily_picks_raw))) if daily_picks_raw else None
        except ValueError:
            daily_picks = None

        manager.upsert(
            user_id=current_user.id,
            risk_profile=risk_profile,
            sectors=sectors or None,
            avoid=avoid or None,
            daily_picks=daily_picks,
        )
        flash("Your preferences are saved — your next daily finder is tailored to them.", "success")
        return redirect(url_for("dashboard.index"))

    prefs = manager.get(current_user.id)
    selected = set((prefs.sectors or "").split(",")) if prefs and prefs.sectors else set()
    is_welcome = request.args.get("welcome") == "1"

    return render_template(
        "preferences.html",
        prefs=prefs,
        risk_profiles=VALID_RISK_PROFILES,
        sector_choices=SECTOR_CHOICES,
        selected_sectors=selected,
        is_welcome=is_welcome,
    )
