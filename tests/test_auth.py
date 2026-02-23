"""Tests for auth endpoints (/token, get_current_user)."""

import pytest
from tests.conftest import (
    TEST_USER,
    create_test_user,
    get_auth_token,
    auth_header,
    create_user_and_login,
)


class TestLogin:
    """POST /token"""

    def test_login_with_valid_username(self, client):
        create_test_user(client)
        response = client.post(
            "/token",
            data={"username": TEST_USER["username"], "password": TEST_USER["password"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_with_valid_email(self, client):
        """The auth endpoint also accepts email in the username field."""
        create_test_user(client)
        response = client.post(
            "/token",
            data={"username": TEST_USER["email"], "password": TEST_USER["password"]},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_with_wrong_password(self, client):
        create_test_user(client)
        response = client.post(
            "/token",
            data={"username": TEST_USER["username"], "password": "WrongPass!1"},
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_with_nonexistent_user(self, client):
        response = client.post(
            "/token",
            data={"username": "ghost", "password": "Whatever1!"},
        )
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        response = client.post("/token", data={})
        assert response.status_code == 422


class TestProtectedAccess:
    """Verify token-based access control."""

    def test_access_protected_route_without_token(self, client):
        response = client.get("/user/get")
        assert response.status_code in (401, 403)

    def test_access_protected_route_with_invalid_token(self, client):
        response = client.get("/user/get", headers=auth_header("invalid.token.value"))
        assert response.status_code == 401

    def test_access_protected_route_with_valid_token(self, client):
        _, token = create_user_and_login(client)
        response = client.get("/user/get", headers=auth_header(token))
        assert response.status_code == 200
        # Verify the token resolved to the correct user
        body = response.json()
        assert body["username"] == TEST_USER["username"]
        assert body["email"] == TEST_USER["email"]

    def test_expired_or_tampered_token(self, client):
        """A manually crafted / tampered JWT should be rejected."""
        tampered = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImZha2UiLCJpZCI6IjAwMDAwMDAwLTAwMDAtMDAwMC0wMDAwLTAwMDAwMDAwMDAwMCJ9.tampered"
        response = client.get("/user/get", headers=auth_header(tampered))
        assert response.status_code == 401
