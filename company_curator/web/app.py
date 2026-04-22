"""Flask application factory.

SRP: Only responsible for creating and configuring the Flask app.
DIP: All dependencies are injected — no concrete implementations imported.
"""

from __future__ import annotations

import anthropic
from flask import Flask

from company_curator.config import Config
from company_curator.data.db import Database
from company_curator.data.fetcher import BaseDataFetcher


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

    # Store dependencies for access in routes
    app.config["APP_CONFIG"] = config
    app.config["APP_DB"] = db
    app.config["APP_FETCHER"] = fetcher
    app.config["APP_CLIENT"] = client

    # Register blueprints
    from company_curator.web.routes.dashboard import dashboard_bp
    from company_curator.web.routes.watchlist import watchlist_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(watchlist_bp, url_prefix="/watchlist")

    return app
