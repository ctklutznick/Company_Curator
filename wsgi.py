"""WSGI entry point for production deployment.

Creates the Flask app with all dependencies wired up.
Optionally starts the APScheduler for daily pipelines.
"""

import os
import sys

import anthropic

from company_curator.config import load_config
from company_curator.data.db import Database
from company_curator.data.fetcher import YFinanceDataFetcher
from company_curator.web.app import create_app


def build_app():
    """Build the Flask app with production dependencies."""
    config = load_config()

    if not config.api.anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    db = Database(config.database_url)
    db.connect()

    client = anthropic.Anthropic(api_key=config.api.anthropic_api_key)
    fetcher = YFinanceDataFetcher()

    app = create_app(config, db, fetcher, client)

    # Start scheduler if enabled
    if os.environ.get("RUN_SCHEDULER", "").lower() in ("1", "true", "yes"):
        from company_curator.scheduler_service import start_scheduler
        start_scheduler(config, db)

    return app


app = build_app()

if __name__ == "__main__":
    app.run()
