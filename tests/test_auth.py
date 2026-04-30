"""Tests for authentication flows."""


def test_login_page_loads(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Log In" in response.data


def test_signup_page_loads(client):
    response = client.get("/auth/signup")
    assert response.status_code == 200
    assert b"Create Account" in response.data


def test_signup_and_login(client):
    # Sign up
    response = client.post("/auth/signup", data={
        "email": "new@example.com",
        "display_name": "New User",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
    }, follow_redirects=True)
    assert response.status_code == 200

    # Log out
    client.get("/auth/logout", follow_redirects=True)

    # Log in
    response = client.post("/auth/login", data={
        "email": "new@example.com",
        "password": "securepassword123",
    }, follow_redirects=True)
    assert response.status_code == 200


def test_signup_password_mismatch(client):
    response = client.post("/auth/signup", data={
        "email": "bad@example.com",
        "display_name": "Bad User",
        "password": "password123",
        "confirm_password": "different123",
    }, follow_redirects=True)
    assert b"Passwords do not match" in response.data


def test_unauthenticated_redirect(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_invalid_login(client):
    response = client.post("/auth/login", data={
        "email": "nobody@example.com",
        "password": "wrongpassword",
    }, follow_redirects=True)
    assert b"Invalid email or password" in response.data
