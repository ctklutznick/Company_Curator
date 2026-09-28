"""Tests for the Terms of Service page and signup acceptance recording."""

from company_curator.data.models import User


def _signup(client, **overrides):
    data = {
        "email": "tos@example.com",
        "display_name": "ToS User",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "accept_terms": "on",
    }
    data.update(overrides)
    return client.post("/auth/signup", data=data, follow_redirects=True)


def test_terms_page_loads(client):
    response = client.get("/terms")
    assert response.status_code == 200
    body = response.data.lower()
    assert b"terms of service" in body
    # The AI usage must be disclosed, and it must be clear this isn't advice.
    assert b"artificial intelligence" in body or b"ai" in body
    assert b"not investment advice" in body


def test_signup_requires_terms_acceptance(client, db):
    response = _signup(client, accept_terms="")
    assert b"must accept the Terms" in response.data
    # No account should be created when terms are not accepted.
    assert db.session.query(User).filter_by(email="tos@example.com").first() is None


def test_signup_records_terms_acceptance(client, db):
    from company_curator.web.routes.legal import TERMS_VERSION

    response = _signup(client)
    assert response.status_code == 200
    user = db.session.query(User).filter_by(email="tos@example.com").first()
    assert user is not None
    assert user.terms_accepted_at  # timestamp recorded
    assert user.terms_version == TERMS_VERSION
