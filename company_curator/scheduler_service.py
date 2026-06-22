"""APScheduler-based scheduler for multi-user daily pipelines.

SRP: Only responsible for scheduling and dispatching per-user pipelines.
DIP: Depends on injected config and database abstractions.
"""

from __future__ import annotations

import threading
import time

import anthropic
from apscheduler.schedulers.background import BackgroundScheduler

from company_curator.config import Config
from company_curator.data.db import Database
from company_curator.data.fetcher import YFinanceDataFetcher
from company_curator.data.models import User
from company_curator.notifications.emailer import EmailNotifier
from company_curator.scheduler import DailyPipeline


def start_scheduler(config: Config, db: Database) -> BackgroundScheduler:
    """Start the background scheduler that runs pipelines for all users."""
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        func=_run_all_users,
        trigger="cron",
        hour=9,
        minute=0,
        day_of_week="mon-fri",
        timezone="America/Los_Angeles",
        args=[config, db],
        id="daily_pipeline",
        replace_existing=True,
    )

    scheduler.start()
    print("[Scheduler] Started — daily pipeline at 9:00 AM Pacific Mon-Fri")
    return scheduler


def run_user_pipeline(config: Config, db: Database, user_id: int) -> None:
    """Run the daily pipeline once for a single user and email them the report."""
    user = db.session.query(User).get(user_id)
    if not user:
        print(f"[Scheduler] No user {user_id}; skipping pipeline.")
        return

    client = anthropic.Anthropic(api_key=config.api.anthropic_api_key)
    fetcher = YFinanceDataFetcher()
    try:
        notifier = EmailNotifier.build_from_user(user, config.fernet_key, config.email)
        pipeline = DailyPipeline(config, db, fetcher, client, notifier, user_id=user.id)
        pipeline.run()
        print(f"[Scheduler] Pipeline complete for user {user.email}")
    except Exception as e:
        print(f"[Scheduler] Pipeline failed for user {user.email}: {e}")


def run_user_pipeline_async(config: Config, db: Database, user_id: int) -> None:
    """Fire-and-forget a single user's pipeline in a background thread.

    Used to send a first report right after onboarding without blocking the web
    request. The thread gets its own thread-local DB session, cleaned up at exit.
    """
    def _worker() -> None:
        try:
            run_user_pipeline(config, db, user_id)
        finally:
            db.close()

    threading.Thread(target=_worker, daemon=True).start()


def _run_all_users(config: Config, db: Database) -> None:
    """Run the daily pipeline for each registered user, staggered."""
    user_ids = [u.id for u in db.session.query(User).all()]
    for i, user_id in enumerate(user_ids):
        if i > 0:
            time.sleep(300)  # 5 min stagger between users
        run_user_pipeline(config, db, user_id)
