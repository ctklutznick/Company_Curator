"""Audit routes — view monthly watchlist audits and respond to drop proposals.

SRP: Only handles audit viewing and drop-response routes.
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from company_curator.watchlist.audit_manager import AuditManager

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("/")
@login_required
def list_all():
    """List all monthly audits."""
    db = current_app.config["APP_DB"]
    audit_mgr = AuditManager(db, current_user.id)
    audits = audit_mgr.list_audits()

    return render_template("audit_list.html", audits=audits)


@audit_bp.route("/<audit_month>")
@login_required
def detail(audit_month: str):
    """View a specific monthly audit."""
    db = current_app.config["APP_DB"]
    audit_mgr = AuditManager(db, current_user.id)
    audit = audit_mgr.get_by_month(audit_month)

    if not audit:
        abort(404)

    return render_template("audit_detail.html", audit=audit)


@audit_bp.route("/<audit_month>/drop/<int:entry_id>", methods=["POST"])
@login_required
def respond_to_drop(audit_month: str, entry_id: int):
    """Accept or reject a drop proposal."""
    db = current_app.config["APP_DB"]
    audit_mgr = AuditManager(db, current_user.id)

    action = request.form.get("action")
    accepted = action == "accept"

    entry = db.fetchone(
        "SELECT * FROM monthly_audit_entries WHERE id = ? AND user_id = ?",
        (entry_id, current_user.id),
    )
    if not entry:
        abort(404)

    audit_mgr.respond_to_drop(entry_id, accepted)

    if accepted:
        flash(f"Dropped {entry['ticker']} from your watchlist.", "success")
    else:
        flash(f"Keeping {entry['ticker']} on your watchlist.", "info")

    return redirect(url_for("audit.detail", audit_month=audit_month))
