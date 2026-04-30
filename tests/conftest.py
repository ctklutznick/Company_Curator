"""Shared test fixtures."""

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("WEB_SECRET_KEY", "test-secret-key")

from company_curator.config import load_config
from company_curator.data.db import Database
from company_curator.data.models import User
from company_curator.web.app import create_app


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def db(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    database = Database(db_url)
    database.connect()
    yield database
    database.close()


@pytest.fixture
def test_user(db):
    from flask_bcrypt import generate_password_hash
    user = User(
        email="test@example.com",
        password_hash=generate_password_hash("testpassword123").decode("utf-8"),
        display_name="Test User",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def app(config, db):
    mock_client = MagicMock()
    mock_fetcher = MagicMock()

    # Patch config with test DB
    from dataclasses import replace
    test_config = replace(config, database_url=str(db.engine.url))

    application = create_app(test_config, db, mock_fetcher, mock_client)
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


@pytest.fixture
def client(app):
    return app.test_client()
