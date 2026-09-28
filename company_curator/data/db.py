"""SQLAlchemy database layer for Company Curator.

SRP: Handles only database connection and session management.
OCP: New tables can be added via models without modifying existing code.
DIP: Other modules receive a Database instance rather than creating connections.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from company_curator.data.models import Base


class Database:
    """Manages SQLAlchemy engine and scoped sessions."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        connect_args: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        self._engine: Engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(bind=self._engine)
        self._scoped_session = scoped_session(self._session_factory)

    def create_tables(self) -> None:
        """Create all tables from ORM models."""
        Base.metadata.create_all(self._engine)

    @property
    def session(self) -> Session:
        """Return the current thread-local session."""
        return self._scoped_session()

    def connect(self) -> None:
        """Initialize — create missing tables, then add any missing columns.

        create_all() never alters existing tables, so a DB created before a
        model gained a column would be missing it. This lightweight, idempotent
        additive migration keeps existing databases (local + the Fly volume) in
        sync with the models without a full Alembic workflow.
        """
        self.create_tables()
        self._add_missing_columns()

    def _add_missing_columns(self) -> None:
        """Add columns present on the ORM models but missing from live tables.

        Additive only: new columns are added as nullable (existing rows get
        NULL). Best-effort — a failure on one column is logged, not fatal.
        """
        inspector = inspect(self._engine)
        with self._engine.begin() as conn:
            for table_name, table in Base.metadata.tables.items():
                if not inspector.has_table(table_name):
                    continue
                existing = {c["name"] for c in inspector.get_columns(table_name)}
                for column in table.columns:
                    if column.name in existing:
                        continue
                    col_type = column.type.compile(dialect=self._engine.dialect)
                    try:
                        conn.execute(
                            text(f'ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}')
                        )
                        print(f"[DB] Added missing column {table_name}.{column.name}")
                    except Exception as e:  # noqa: BLE001 — never block startup
                        print(f"[DB] Could not add {table_name}.{column.name}: {e}")

    def close(self) -> None:
        """Remove the current scoped session."""
        self._scoped_session.remove()

    @property
    def engine(self) -> Engine:
        return self._engine

    # --- Compatibility layer (raw SQL) ---
    # These methods allow gradual migration from raw SQL to ORM queries.
    # Routes and managers can use either the ORM (db.session) or raw SQL (db.execute).

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute raw SQL. Use '?' placeholders (auto-converted to ':paramN' for SA)."""
        sa_sql, sa_params = self._convert_params(sql, params)
        result = self.session.execute(text(sa_sql), sa_params)
        self.session.flush()
        return result

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        sa_sql, sa_params = self._convert_params(sql, params)
        result = self.session.execute(text(sa_sql), sa_params)
        row = result.mappings().first()
        return row

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        sa_sql, sa_params = self._convert_params(sql, params)
        result = self.session.execute(text(sa_sql), sa_params)
        return list(result.mappings().all())

    def commit(self) -> None:
        self.session.commit()

    @staticmethod
    def _convert_params(sql: str, params: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
        """Convert '?' placeholder SQL to ':paramN' named parameters for SQLAlchemy."""
        sa_params: dict[str, Any] = {}
        idx = 0
        converted = []
        i = 0
        while i < len(sql):
            if sql[i] == "?" and (i == 0 or sql[i - 1] != "'"):
                param_name = f"p{idx}"
                converted.append(f":{param_name}")
                if idx < len(params):
                    sa_params[param_name] = params[idx]
                idx += 1
            else:
                converted.append(sql[i])
            i += 1
        return "".join(converted), sa_params

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        self.close()
