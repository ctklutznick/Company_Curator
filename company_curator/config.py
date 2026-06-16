"""Configuration management for Company Curator.

SRP: This module's sole responsibility is loading and providing configuration.
DIP: Other modules depend on the Config abstraction, not on os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import requests
from dotenv import load_dotenv


def _detect_ngrok_url() -> str | None:
    """Check if ngrok is running and return its public URL."""
    try:
        resp = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=1)
        tunnels = resp.json().get("tunnels", [])
        for t in tunnels:
            if t.get("proto") == "https":
                return t["public_url"]
    except Exception:
        pass
    return None


@dataclass(frozen=True)
class ApiConfig:
    anthropic_api_key: str


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_to: str


@dataclass(frozen=True)
class DiscoveryConfig:
    daily_picks: int = 3
    min_market_cap: float = 500_000_000  # $500M minimum
    min_volume: int = 100_000  # Minimum avg daily volume
    dedup_days: int = 30  # Don't re-recommend a ticker within this window


@dataclass(frozen=True)
class WatchlistConfig:
    monitoring_period_days: int = 90  # 3 months
    min_price_growth_pct: float = 15.0  # Minimum price appreciation
    min_revenue_growth_pct: float = 10.0  # Minimum revenue growth


@dataclass(frozen=True)
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 5050
    base_url: str = "http://127.0.0.1:5050"
    secret_key: str = "company-curator-dev-key"


@dataclass(frozen=True)
class Config:
    api: ApiConfig
    email: EmailConfig
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database_url: str = "sqlite:///company_curator.db"
    reports_dir: Path = Path("reports")
    fernet_key: str = ""


def load_config(env_path: Path | None = None) -> Config:
    """Load configuration from environment variables and .env file."""
    load_dotenv(env_path)

    api = ApiConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    email = EmailConfig(
        smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=os.environ.get("EMAIL_ADDRESS", ""),
        smtp_password=os.environ.get("EMAIL_PASSWORD", ""),
        email_to=os.environ.get("EMAIL_RECIPIENT", ""),
    )

    explicit_base_url = os.environ.get("WEB_BASE_URL")
    port = int(os.environ.get("WEB_PORT", "5050"))
    if explicit_base_url:
        base_url = explicit_base_url
    else:
        ngrok_url = _detect_ngrok_url()
        base_url = ngrok_url or f"http://127.0.0.1:{port}"

    web = WebConfig(
        host=os.environ.get("WEB_HOST", "0.0.0.0"),
        port=port,
        base_url=base_url,
        secret_key=os.environ.get("WEB_SECRET_KEY", "company-curator-dev-key"),
    )

    return Config(
        api=api,
        email=email,
        web=web,
        database_url=os.environ.get("DATABASE_URL", "sqlite:///company_curator.db"),
        fernet_key=os.environ.get("FERNET_KEY", ""),
    )
