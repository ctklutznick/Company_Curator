"""Legal / informational pages (Terms of Service).

SRP: Only serves static legal pages. No auth, DB, or business logic here.
OCP: Add a /privacy route here later without touching other blueprints.
"""

from __future__ import annotations

from flask import Blueprint, render_template

legal_bp = Blueprint("legal", __name__)

# Bump this when the Terms of Service change materially. It is recorded per
# user at signup (User.terms_version), so a future change can be used to
# re-prompt existing users for acceptance.
TERMS_VERSION = "2026-09-28"


@legal_bp.route("/terms")
def terms():
    """Public Terms of Service page — must be readable before signing up."""
    return render_template("terms.html", terms_version=TERMS_VERSION)
