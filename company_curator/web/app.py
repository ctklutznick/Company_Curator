"""Flask application factory.

SRP: Only responsible for creating and configuring the Flask app.
DIP: All dependencies are injected — no concrete implementations imported.
"""

from __future__ import annotations

import re

import anthropic
from flask import Flask
from markupsafe import Markup

from company_curator.config import Config
from company_curator.data.db import Database
from company_curator.data.fetcher import BaseDataFetcher


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

    # Register markdown filter for templates
    app.jinja_env.filters["md_to_html"] = _md_to_html

    # Store dependencies for access in routes
    app.config["APP_CONFIG"] = config
    app.config["APP_DB"] = db
    app.config["APP_FETCHER"] = fetcher
    app.config["APP_CLIENT"] = client

    # Register blueprints
    from company_curator.web.routes.ai_chat import ai_chat_bp
    from company_curator.web.routes.dashboard import dashboard_bp
    from company_curator.web.routes.reports import reports_bp
    from company_curator.web.routes.watchlist import watchlist_bp

    app.register_blueprint(ai_chat_bp, url_prefix="/ai")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(reports_bp, url_prefix="/report")
    app.register_blueprint(watchlist_bp, url_prefix="/watchlist")

    return app
