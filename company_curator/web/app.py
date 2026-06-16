"""Flask application factory.

SRP: Only responsible for creating and configuring the Flask app.
DIP: All dependencies are injected — no concrete implementations imported.
"""

from __future__ import annotations

import re
from datetime import timedelta

import anthropic
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from markupsafe import Markup

from company_curator.config import Config
from company_curator.data.db import Database
from company_curator.data.fetcher import BaseDataFetcher
from company_curator.data.models import User


def _md_to_html(text: str) -> Markup:
    """Convert markdown text to styled HTML for report display."""
    if not text:
        return Markup("")

    lines = text.split("\n")
    html_lines: list[str] = []
    in_list = False
    list_type = ""
    i = 0

    while i < len(lines):
        line = lines[i]

        # Markdown table
        if "|" in line and i + 1 < len(lines) and re.match(r"\s*\|[-\s|:]+\|\s*$", lines[i + 1]):
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            # Parse header
            headers = [h.strip() for h in line.strip().strip("|").split("|")]
            i += 2  # skip separator
            rows: list[list[str]] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            html_lines.append('<table><thead><tr>')
            for h in headers:
                html_lines.append(f'<th>{_md_inline(h)}</th>')
            html_lines.append('</tr></thead><tbody>')
            for row in rows:
                html_lines.append('<tr>')
                for cell in row:
                    html_lines.append(f'<td>{_md_inline(cell)}</td>')
                html_lines.append('</tr>')
            html_lines.append('</tbody></table>')
            continue

        # Close list if needed
        if in_list and not re.match(r"^\s*[-*]\s", line) and not re.match(r"^\s*\d+\.\s", line) and line.strip():
            html_lines.append(f"</{list_type}>")
            in_list = False

        if line.startswith("#### "):
            html_lines.append(f'<h4 class="rpt-h4">{_md_inline(line[5:])}</h4>')
        elif line.startswith("### "):
            html_lines.append(f'<h3 class="rpt-h3">{_md_inline(line[4:])}</h3>')
        elif line.startswith("## "):
            html_lines.append(f'<h2 class="rpt-h2">{_md_inline(line[3:])}</h2>')
        elif line.startswith("# "):
            html_lines.append(f'<h1 class="rpt-h1">{_md_inline(line[2:])}</h1>')
        elif re.match(r"^\s*[-*]\s", line):
            content = re.sub(r"^\s*[-*]\s", "", line)
            if not in_list or list_type != "ul":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            html_lines.append(f"<li>{_md_inline(content)}</li>")
        elif re.match(r"^\s*\d+\.\s", line):
            content = re.sub(r"^\s*\d+\.\s", "", line)
            if not in_list or list_type != "ol":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            html_lines.append(f"<li>{_md_inline(content)}</li>")
        elif not line.strip():
            pass
        else:
            html_lines.append(f"<p>{_md_inline(line)}</p>")

        i += 1

    if in_list:
        html_lines.append(f"</{list_type}>")

    return Markup("\n".join(html_lines))


def _md_inline(text: str) -> str:
    """Convert inline markdown formatting."""
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(
        r"`(.+?)`",
        r'<code style="font-family:\'JetBrains Mono\',monospace;background:var(--paper-2);padding:1px 5px;border-radius:3px;font-size:12px;">\1</code>',
        text,
    )
    # Risk styling
    text = re.sub(r"\bHIGH RISK\b", '<span style="color:var(--accent-red);font-weight:600;">HIGH RISK</span>', text)
    text = re.sub(r"\bHIGH\b", '<span style="color:var(--accent-red);font-weight:600;">HIGH</span>', text)
    text = re.sub(r"\bMEDIUM\b", '<span style="color:#d69e2e;font-weight:600;">MEDIUM</span>', text)
    text = re.sub(r"\bLOW\b", '<span style="color:var(--accent-green);font-weight:600;">LOW</span>', text)
    return text


def create_app(
    config: Config,
    db: Database,
    fetcher: BaseDataFetcher,
    client: anthropic.Anthropic,
) -> Flask:
    """Create the Flask application with injected dependencies."""
    app = Flask(
        __name__,
        template_folder="templates",
    )
    app.secret_key = config.web.secret_key

    # Session cookie security
    app.config["SESSION_COOKIE_SECURE"] = not config.web.base_url.startswith("http://127")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=7)
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

    # CSRF protection
    csrf = CSRFProtect(app)

    # Bcrypt for password hashing
    bcrypt = Bcrypt(app)
    app.extensions["bcrypt"] = bcrypt

    # Flask-Login
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.query(User).get(int(user_id))

    # Rate limiting
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per hour"],
        storage_uri="memory://",
    )

    # Register markdown filter for templates
    app.jinja_env.filters["md_to_html"] = _md_to_html

    # Store dependencies for access in routes
    app.config["APP_CONFIG"] = config
    app.config["APP_DB"] = db
    app.config["APP_FETCHER"] = fetcher
    app.config["APP_CLIENT"] = client

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if config.web.base_url.startswith("https://"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Register blueprints
    from company_curator.web.routes.ai_chat import ai_chat_bp
    from company_curator.web.routes.auth import auth_bp
    from company_curator.web.routes.dashboard import dashboard_bp
    from company_curator.web.routes.preferences import preferences_bp
    from company_curator.web.routes.reports import reports_bp
    from company_curator.web.routes.audit import audit_bp
    from company_curator.web.routes.watchlist import watchlist_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(ai_chat_bp, url_prefix="/ai")
    app.register_blueprint(audit_bp, url_prefix="/audit")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(preferences_bp, url_prefix="/preferences")
    app.register_blueprint(reports_bp, url_prefix="/report")
    app.register_blueprint(watchlist_bp, url_prefix="/watchlist")

    # Exempt AJAX endpoints from CSRF (they use custom header instead)
    csrf.exempt(ai_chat_bp)

    # Apply rate limits to sensitive endpoints
    limiter.limit("5 per minute")(auth_bp)
    limiter.limit("20 per hour")(ai_chat_bp)

    # Dev auto-login: when running locally, auto-log in the default user
    is_local = config.web.base_url.startswith("http://127") or config.web.base_url.startswith("http://localhost")
    if is_local:
        from flask_login import current_user, login_user

        @app.before_request
        def dev_auto_login():
            if not current_user.is_authenticated:
                user = db.session.query(User).get(1)
                if user:
                    login_user(user, remember=True)

    # Tear down scoped session at end of request
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.close()

    return app
