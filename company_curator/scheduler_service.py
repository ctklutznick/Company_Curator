"""APScheduler-based scheduler for multi-user daily pipelines.

SRP: Only responsible for scheduling and dispatching per-user pipelines.
DIP: Depends on injected config and database abstractions.
"""

from __future__ import annotations

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
        hour=7,
        minute=0,
        day_of_week="mon-fri",
        args=[config, db],
        id="daily_pipeline",
        replace_existing=True,
    )

    scheduler.start()
    print("[Scheduler] Started — daily pipeline at 7:00 AM Mon-Fri")
    return scheduler


def _run_all_users(config: Config, db: Database) -> None:
    """Run the daily pipeline for each registered user, staggered."""
    import time

    users = db.session.query(User).all()
    client = anthropic.Anthropic(api_key=config.api.anthropic_api_key)
    fetcher = YFinanceDataFetcher()

    for i, user in enumerate(users):
        if i > 0:
            time.sleep(300)  # 5 min stagger between users

        try:
            notifier = EmailNotifier.build_from_user(user, config.fernet_key, config.email)
            pipeline = DailyPipeline(config, db, fetcher, client, notifier, user_id=user.id)
            pipeline.run()
            print(f"[Scheduler] Pipeline complete for user {user.email}")
        except Exception as e:
            print(f"[Scheduler] Pipeline failed for user {user.email}: {e}")
