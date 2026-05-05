"""Tests for user endpoints (/user/*)."""

import pytest
from tests.conftest import (
    TEST_USER,
    TEST_USER_2,
    create_test_user,
    get_auth_token,
    auth_header,
    create_user_and_login,
)


# ── POST /user/create ────────────────────────────────────────────────────────

class TestCreateUser:

    def test_create_user_success(self, client):
        resp = create_test_user(client)["response"]
        assert resp.status_code == 200
        assert resp.json()["message"] == "Account created successfully."

        # Verify the user was actually stored with the correct data
        token = get_auth_token(client, TEST_USER["username"], TEST_USER["password"])
        get_resp = client.get("/user/get", headers=auth_header(token))
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["username"] == TEST_USER["username"]
        assert body["email"] == TEST_USER["email"]
        assert "id" in body
        assert "registered_at" in body

    def test_create_user_invalid_email(self, client):
        data = {**TEST_USER, "email": "not-an-email"}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400
        assert "valid email" in resp.json()["detail"].lower()

    def test_create_user_empty_email(self, client):
        data = {**TEST_USER, "email": ""}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400

    def test_create_user_weak_password_too_short(self, client):
        data = {**TEST_USER, "password": "Ab1!"}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400
        assert "Password must be" in resp.json()["detail"]

    def test_create_user_weak_password_no_uppercase(self, client):
        data = {**TEST_USER, "password": "lowercase1!"}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400

    def test_create_user_weak_password_no_lowercase(self, client):
        data = {**TEST_USER, "password": "UPPERCASE1!"}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400

    def test_create_user_weak_password_no_digit(self, client):
        data = {**TEST_USER, "password": "NoDigitsHere!"}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400

    def test_create_user_weak_password_no_symbol(self, client):
        data = {**TEST_USER, "password": "NoSymbols1a"}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400

    def test_create_user_password_too_long(self, client):
        long_pw = "Aa1!" + "x" * 70  # 74 chars, exceeds 72
        data = {**TEST_USER, "password": long_pw}
        resp = client.post("/user/create", json=data)
        assert resp.status_code == 400

    def test_create_user_duplicate_email(self, client):
        create_test_user(client)
        duplicate = {**TEST_USER, "username": "other_user"}
        resp = client.post("/user/create", json=duplicate)
        assert resp.status_code == 400
        assert "Email already in use" in resp.json()["detail"]

    def test_create_user_missing_fields(self, client):
        resp = client.post("/user/create", json={})
        assert resp.status_code == 422

    def test_create_user_missing_password(self, client):
        resp = client.post("/user/create", json={"username": "u", "email": "a@b.com"})
        assert resp.status_code == 422


# ── GET /user/get ─────────────────────────────────────────────────────────────

class TestGetUser:

    def test_get_user_details_authenticated(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/user/get", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == TEST_USER["username"]
        assert body["email"] == TEST_USER["email"]
        assert "id" in body
        assert "registered_at" in body

    def test_get_user_details_unauthenticated(self, client):
        resp = client.get("/user/get")
        assert resp.status_code in (401, 403)

    def test_get_user_returns_correct_user(self, client):
        """When two users exist, /user/get returns the authenticated one."""
        create_test_user(client, TEST_USER)
        create_test_user(client, TEST_USER_2)
        token = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])
        resp = client.get("/user/get", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == TEST_USER_2["username"]
        assert body["email"] == TEST_USER_2["email"]
        # Must NOT return the other user's data
        assert body["username"] != TEST_USER["username"]
        assert body["email"] != TEST_USER["email"]


# ── PATCH /user/update/ ──────────────────────────────────────────────────────

class TestUpdateUser:

    def test_update_username(self, client):
        user_data, token = create_user_and_login(client)
        resp = client.get("/user/get", headers=auth_header(token))
        user_id = resp.json()["id"]

        resp = client.patch(
            "/user/update/",
            json={"id": user_id, "username": "newname"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        # Verify the change persisted
        resp = client.get("/user/get", headers=auth_header(token))
        assert resp.json()["username"] == "newname"

    def test_update_email_valid(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/user/get", headers=auth_header(token))
        user_id = resp.json()["id"]

        resp = client.patch(
            "/user/update/",
            json={"id": user_id, "email": "newemail@example.com"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        resp = client.get("/user/get", headers=auth_header(token))
        assert resp.json()["email"] == "newemail@example.com"

    def test_update_email_invalid(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/user/get", headers=auth_header(token))
        user_id = resp.json()["id"]

        resp = client.patch(
            "/user/update/",
            json={"id": user_id, "email": "bad-email"},
            headers=auth_header(token),
        )
        assert resp.status_code == 400

    def test_update_email_duplicate(self, client):
        """Cannot update email to one already owned by another user."""
        create_test_user(client, TEST_USER)
        create_test_user(client, TEST_USER_2)
        token = get_auth_token(client, TEST_USER["username"], TEST_USER["password"])

        resp = client.get("/user/get", headers=auth_header(token))
        user_id = resp.json()["id"]

        resp = client.patch(
            "/user/update/",
            json={"id": user_id, "email": TEST_USER_2["email"]},
            headers=auth_header(token),
        )
        assert resp.status_code == 400
        assert "Email already in use" in resp.json()["detail"]

    def test_update_password_valid(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/user/get", headers=auth_header(token))
        user_id = resp.json()["id"]

        new_password = "NewStrong1!"
        resp = client.patch(
            "/user/update/",
            json={"id": user_id, "password": new_password},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        # Should be able to login with new password
        resp = client.post(
            "/token",
            data={"username": TEST_USER["username"], "password": new_password},
        )
        assert resp.status_code == 200

    def test_update_password_weak(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/user/get", headers=auth_header(token))
        user_id = resp.json()["id"]

        resp = client.patch(
            "/user/update/",
            json={"id": user_id, "password": "weak"},
            headers=auth_header(token),
        )
        assert resp.status_code == 400

    def test_update_user_unauthenticated(self, client):
        resp = client.patch(
            "/user/update/",
            json={"id": "00000000-0000-0000-0000-000000000000", "username": "x"},
        )
        assert resp.status_code in (401, 403)

    def test_update_no_changes(self, client):
        """Sending an update with no optional fields should still succeed."""
        _, token = create_user_and_login(client)
        resp = client.get("/user/get", headers=auth_header(token))
        user_id = resp.json()["id"]

        resp = client.patch(
            "/user/update/",
            json={"id": user_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

    def test_update_no_id_required(self, client):
        """The authenticated user can update profile fields without sending an id."""
        _, token = create_user_and_login(client)

        resp = client.patch(
            "/user/update/",
            json={"username": "newname"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        resp = client.get("/user/get", headers=auth_header(token))
        assert resp.json()["username"] == "newname"
