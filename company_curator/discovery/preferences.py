"""Per-user discovery preferences.

SRP: Only responsible for reading/writing user preferences and resolving
the risk profile into concrete screening parameters.
DIP: Receives a Database instance via injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from company_curator.data.db import Database
from company_curator.data.models import UserPreferences

VALID_RISK_PROFILES = ("conservative", "moderate", "aggressive")

# Option B: risk profile maps to concrete screening thresholds.
# min_market_cap in dollars; min_revenue_growth as a fraction (0.05 == 5%).
_RISK_DEFAULTS: dict[str, tuple[float, float]] = {
    "conservative": (10_000_000_000, 0.05),  # large, established companies
    "moderate": (2_000_000_000, 0.10),
    "aggressive": (300_000_000, 0.20),  # smaller, faster-growing companies
}


@dataclass(frozen=True)
class ResolvedPreferences:
    """Effective preferences with all fallbacks already applied."""

    risk_profile: str
    sectors: str | None
    avoid: str | None
    daily_picks: int
    min_market_cap: float
    min_revenue_growth: float  # fraction, e.g. 0.10


class PreferencesManager:
    """Reads, writes, and resolves per-user discovery preferences."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, user_id: int) -> UserPreferences | None:
        return (
            self._db.session.query(UserPreferences)
            .filter_by(user_id=user_id)
            .first()
        )

    def resolve(self, user_id: int, default_daily_picks: int) -> ResolvedPreferences:
        """Return effective preferences, deriving numeric thresholds from the
        risk profile when not explicitly set. Falls back to a moderate profile
        when the user has no preferences row yet."""
        prefs = self.get(user_id)

        if prefs is None:
            cap, growth = _RISK_DEFAULTS["moderate"]
            return ResolvedPreferences(
                risk_profile="moderate",
                sectors=None,
                avoid=None,
                daily_picks=default_daily_picks,
                min_market_cap=cap,
                min_revenue_growth=growth,
            )

        risk = prefs.risk_profile if prefs.risk_profile in _RISK_DEFAULTS else "moderate"
        default_cap, default_growth = _RISK_DEFAULTS[risk]

        return ResolvedPreferences(
            risk_profile=risk,
            sectors=prefs.sectors or None,
            avoid=prefs.avoid or None,
            daily_picks=prefs.daily_picks or default_daily_picks,
            min_market_cap=prefs.min_market_cap or default_cap,
            min_revenue_growth=(
                prefs.min_revenue_growth_pct / 100.0
                if prefs.min_revenue_growth_pct is not None
                else default_growth
            ),
        )

    def upsert(
        self,
        user_id: int,
        risk_profile: str,
        sectors: str | None,
        avoid: str | None,
        daily_picks: int | None,
    ) -> UserPreferences:
        """Create or update a user's preferences and mark them onboarded."""
        if risk_profile not in VALID_RISK_PROFILES:
            risk_profile = "moderate"

        prefs = self.get(user_id)
        if prefs is None:
            prefs = UserPreferences(user_id=user_id)
            self._db.session.add(prefs)

        prefs.risk_profile = risk_profile
        prefs.sectors = sectors or None
        prefs.avoid = avoid or None
        prefs.daily_picks = daily_picks
        prefs.onboarded_at = datetime.utcnow().isoformat(timespec="seconds")

        self._db.session.commit()
        return prefs
