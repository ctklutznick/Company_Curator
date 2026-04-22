"""SQLite database layer for Company Curator.

SRP: Handles only database connection and schema management.
OCP: New tables can be added via migrations without modifying existing code.
DIP: Other modules receive a Database instance rather than creating connections.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any


class Database:
    """Manages SQLite connections with thread-safe access."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._local = threading.local()

    def connect(self) -> None:
        self._get_or_create_connection()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        return self._get_or_create_connection()

    def _get_or_create_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
            self._initialize_schema()
        return conn

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        return self.connection.executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    def commit(self) -> None:
        self.connection.commit()

    def _initialize_schema(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL UNIQUE,
                company_name TEXT NOT NULL,
                added_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_revenue REAL,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                close_price REAL NOT NULL,
                volume INTEGER,
                UNIQUE(ticker, date),
                FOREIGN KEY (ticker) REFERENCES watchlist(ticker)
            );

            CREATE TABLE IF NOT EXISTS daily_picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                company_name TEXT NOT NULL,
                score REAL,
                reasoning TEXT,
                deep_dive TEXT,
                peer_comparison TEXT,
                short_report TEXT,
                UNIQUE(date, ticker)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                triggered_date TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (ticker) REFERENCES watchlist(ticker)
            );

            CREATE TABLE IF NOT EXISTS daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open_price REAL,
                close_price REAL,
                high_price REAL,
                low_price REAL,
                volume INTEGER,
                UNIQUE(ticker, date)
            );

            CREATE TABLE IF NOT EXISTS movement_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                period TEXT NOT NULL DEFAULT 'daily',
                price_change_pct REAL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(ticker, date, period)
            );
        """)

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        self.close()
