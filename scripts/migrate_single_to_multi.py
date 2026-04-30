#!/usr/bin/env python3
"""One-time migration: convert single-user SQLite DB to multi-user schema.

Creates a default user (id=1) and assigns all existing data to that user.
Run this ONCE before switching to the new multi-user codebase.

Usage:
    python scripts/migrate_single_to_multi.py [--db company_curator.db]
"""

import argparse
import sqlite3
import sys
from datetime import datetime


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")

    # Check if already migrated
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        print("Database already has 'users' table — appears to be migrated already.")
        sys.exit(0)

    print(f"Migrating {db_path} to multi-user schema...")

    # 1. Create users table
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            smtp_host TEXT,
            smtp_port INTEGER,
            smtp_user TEXT,
            smtp_password_encrypted TEXT,
            email_to TEXT
        )
    """)

    # 2. Insert default user
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO users (id, email, password_hash, display_name, created_at) VALUES (?, ?, ?, ?, ?)",
        (1, "cli@localhost", "migrated-no-login", "Default User", now),
    )

    # 3. Add user_id column to all data tables
    tables_to_update = [
        "watchlist", "price_history", "daily_picks", "alerts", "daily_prices", "movement_notes"
    ]

    for table in tables_to_update:
        # Check if table exists
        cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            print(f"  Skipping {table} (does not exist)")
            continue

        # Check if user_id already exists
        cursor = conn.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if "user_id" in columns:
            print(f"  Skipping {table} (already has user_id)")
            continue

        print(f"  Adding user_id to {table}...")
        conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER DEFAULT 1 REFERENCES users(id)")
        conn.execute(f"UPDATE {table} SET user_id = 1")

    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    conn.close()

    print("Migration complete. Default user (id=1) created and all data assigned.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate single-user DB to multi-user")
    parser.add_argument("--db", default="company_curator.db", help="Path to SQLite database")
    args = parser.parse_args()
    migrate(args.db)
