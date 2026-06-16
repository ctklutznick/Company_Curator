"""Authentication routes — signup, login, logout, settings.

SRP: Only handles authentication and user settings routes.
"""

from __future__ import annotations

import hmac
import re

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import current_user, login_required, login_user, logout_user

from company_curator.data.models import User

auth_bp = Blueprint("auth", __name__)


def _get_bcrypt() -> Bcrypt:
    return current_app.extensions["bcrypt"]


def _send_welcome_email(user: User) -> None:
    """Send the onboarding welcome email to a new user via the global SMTP
    account, linking them to the preferences questionnaire. Best-effort: never
    blocks signup if email fails."""
    from dataclasses import replace

    from company_curator.notifications.emailer import (
        EmailNotifier,
        welcome_email_markdown,
    )

    config = current_app.config["APP_CONFIG"]
    try:
        preferences_url = f"{config.web.base_url}/preferences/?welcome=1"
        notifier = EmailNotifier(replace(config.email, email_to=user.email))
        notifier.send(
            subject="Welcome to Company Curator — set up your picks",
            body=welcome_email_markdown(user.display_name, preferences_url),
        )
    except Exception as e:  # noqa: BLE001 — email must never break signup
        print(f"[Auth] Failed to send welcome email to {user.email}: {e}")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html")

        db = current_app.config["APP_DB"]
        user = db.session.query(User).filter_by(email=email).first()

        if user and _get_bcrypt().check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    invite_required = current_app.config["APP_CONFIG"].web.signup_invite_code

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if invite_required:
            submitted_code = request.form.get("invite_code", "").strip()
            if not hmac.compare_digest(submitted_code, invite_required):
                errors.append("A valid invite code is required.")
        if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("A valid email is required.")
        if not display_name or len(display_name) > 100:
            errors.append("Display name is required (max 100 chars).")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("signup.html", invite_required=bool(invite_required))

        db = current_app.config["APP_DB"]
        existing = db.session.query(User).filter_by(email=email).first()
        if existing:
            flash("An account with that email already exists.", "error")
            return render_template("signup.html", invite_required=bool(invite_required))

        pw_hash = _get_bcrypt().generate_password_hash(password).decode("utf-8")
        user = User(email=email, password_hash=pw_hash, display_name=display_name)
        db.session.add(user)
        db.session.commit()

        _send_welcome_email(user)

        login_user(user, remember=True)
        flash(f"Welcome, {display_name}!", "success")
        return redirect(url_for("preferences.edit", welcome=1))

    return render_template("signup.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = current_app.config["APP_DB"]
    user = db.session.query(User).get(current_user.id)

    if request.method == "POST":
        user.display_name = request.form.get("display_name", "").strip() or user.display_name
        user.smtp_host = request.form.get("smtp_host", "").strip() or None
        smtp_port_str = request.form.get("smtp_port", "").strip()
        user.smtp_port = int(smtp_port_str) if smtp_port_str else None
        user.smtp_user = request.form.get("smtp_user", "").strip() or None
        user.email_to = request.form.get("email_to", "").strip() or None

        # Only update SMTP password if provided
        smtp_password = request.form.get("smtp_password", "").strip()
        if smtp_password:
            fernet_key = current_app.config["APP_CONFIG"].fernet_key
            if fernet_key:
                from company_curator.utils.crypto import encrypt
                user.smtp_password_encrypted = encrypt(smtp_password, fernet_key)
            else:
                flash("FERNET_KEY not configured — SMTP password cannot be encrypted.", "error")

        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("auth.settings"))

    return render_template("settings.html", user=user)
