"""SQLAlchemy ORM models for Company Curator.

SRP: Defines the database schema as ORM models.
OCP: New models can be added without modifying existing ones.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Per-user SMTP settings (nullable — falls back to global config)
    smtp_host = Column(String(255))
    smtp_port = Column(Integer)
    smtp_user = Column(String(255))
    smtp_password_encrypted = Column(Text)  # Fernet-encrypted
    email_to = Column(String(255))

    # Relationships
    watchlist_entries = relationship("Watchlist", back_populates="user", lazy="dynamic")
    daily_picks = relationship("DailyPick", back_populates="user", lazy="dynamic")
    alerts = relationship("AlertModel", back_populates="user", lazy="dynamic")

    @property
    def is_active(self) -> bool:
        return True

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    company_name = Column(String(255), nullable=False)
    added_date = Column(String(30), nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_revenue = Column(Float)
    status = Column(String(20), nullable=False, server_default="active")
    notes = Column(Text)
    created_at = Column(String(30), nullable=False, server_default="''")  # Set by app

    user = relationship("User", back_populates="watchlist_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_user_ticker"),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    date = Column(String(10), nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer)

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", "date", name="uq_user_price_history"),
    )


class DailyPick(Base):
    __tablename__ = "daily_picks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)
    ticker = Column(String(10), nullable=False)
    company_name = Column(String(255), nullable=False)
    score = Column(Float)
    reasoning = Column(Text)
    deep_dive = Column(Text)
    peer_comparison = Column(Text)
    short_report = Column(Text)

    user = relationship("User", back_populates="daily_picks")

    __table_args__ = (
        UniqueConstraint("user_id", "date", "ticker", name="uq_user_daily_pick"),
    )


class AlertModel(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    alert_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    triggered_date = Column(String(30), nullable=False)
    acknowledged = Column(Integer, nullable=False, server_default="0")

    user = relationship("User", back_populates="alerts")


class DailyPriceModel(Base):
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    date = Column(String(10), nullable=False)
    open_price = Column(Float)
    close_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    volume = Column(Integer)

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", "date", name="uq_user_daily_price"),
    )


class MovementNote(Base):
    __tablename__ = "movement_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    date = Column(String(10), nullable=False)
    period = Column(String(20), nullable=False, server_default="daily")
    price_change_pct = Column(Float)
    note = Column(Text, nullable=False)
    created_at = Column(String(30), nullable=False, server_default="''")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", "date", "period", name="uq_user_movement_note"),
    )
