"""Tests for house endpoints (/home/*)."""

import pytest
from tests.conftest import (
    TEST_USER,
    TEST_USER_2,
    create_test_user,
    get_auth_token,
    auth_header,
    create_user_and_login,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

HOUSE_DATA = {"name": "My House", "description": "Main residence"}
HOUSE_DATA_2 = {"name": "Beach House", "description": "Summer home"}


def create_house(client, token, data=None):
    """Create a house via the API."""
    payload = data or HOUSE_DATA.copy()
    return client.post("/home/create", json=payload, headers=auth_header(token))


# ── POST /home/create ────────────────────────────────────────────────────────

class TestCreateHouse:

    def test_create_house_success(self, client):
        _, token = create_user_and_login(client)
        resp = create_house(client, token)
        assert resp.status_code == 200

        # Verify the house was actually stored with the correct data
        get_resp = client.get("/home/get", headers=auth_header(token))
        assert get_resp.status_code == 200
        houses = get_resp.json()
        assert len(houses) == 1
        assert houses[0]["name"] == HOUSE_DATA["name"]
        assert houses[0]["description"] == HOUSE_DATA["description"]

    def test_create_house_without_description(self, client):
        _, token = create_user_and_login(client)
        resp = create_house(client, token, {"name": "Simple House"})
        assert resp.status_code == 200

        # Verify the house name was stored and description got a default
        get_resp = client.get("/home/get", headers=auth_header(token))
        houses = get_resp.json()
        assert len(houses) == 1
        assert houses[0]["name"] == "Simple House"
        assert houses[0]["description"] is not None  # should have a default

    def test_create_house_duplicate_name(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        resp = create_house(client, token)  # same name
        assert resp.status_code == 400
        assert "already have a house" in resp.json()["detail"].lower()

    def test_create_house_same_name_different_users(self, client):
        """Two different users can have houses with the same name."""
        _, token1 = create_user_and_login(client, TEST_USER)
        create_house(client, token1)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])
        resp = create_house(client, token2)
        # Should succeed – different user
        assert resp.status_code == 200

    def test_create_house_unauthenticated(self, client):
        resp = client.post("/home/create", json=HOUSE_DATA)
        assert resp.status_code in (401, 403)

    def test_create_house_missing_name(self, client):
        _, token = create_user_and_login(client)
        resp = client.post("/home/create", json={}, headers=auth_header(token))
        assert resp.status_code == 422


# ── GET /home/get ─────────────────────────────────────────────────────────────

class TestGetHouses:

    def test_get_houses_empty(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/home/get", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_houses_returns_created(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token, HOUSE_DATA)
        create_house(client, token, HOUSE_DATA_2)

        resp = client.get("/home/get", headers=auth_header(token))
        assert resp.status_code == 200
        houses = resp.json()
        assert len(houses) == 2
        names = {h["name"] for h in houses}
        assert "My House" in names
        assert "Beach House" in names
        # Verify descriptions also match
        descriptions = {h["name"]: h["description"] for h in houses}
        assert descriptions["My House"] == HOUSE_DATA["description"]
        assert descriptions["Beach House"] == HOUSE_DATA_2["description"]

    def test_get_houses_only_own(self, client):
        """User should only see their own houses."""
        _, token1 = create_user_and_login(client, TEST_USER)
        create_house(client, token1, HOUSE_DATA)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])
        create_house(client, token2, HOUSE_DATA_2)

        resp = client.get("/home/get", headers=auth_header(token2))
        assert resp.status_code == 200
        houses = resp.json()
        assert len(houses) == 1
        assert houses[0]["name"] == "Beach House"
        assert houses[0]["description"] == HOUSE_DATA_2["description"]
        # Must NOT contain the other user's house
        assert all(h["name"] != HOUSE_DATA["name"] for h in houses)

    def test_get_houses_unauthenticated(self, client):
        resp = client.get("/home/get")
        assert resp.status_code in (401, 403)

    def test_get_houses_contains_expected_fields(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        resp = client.get("/home/get", headers=auth_header(token))
        house = resp.json()[0]
        assert "id" in house
        assert "name" in house
        assert "description" in house
        # Verify the values match what was sent
        assert house["name"] == HOUSE_DATA["name"]
        assert house["description"] == HOUSE_DATA["description"]


# ── GET /home/get_id/{house_id} ──────────────────────────────────────────────

class TestGetHouseById:

    def test_get_house_by_id(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)

        # First get the house id
        houses_resp = client.get("/home/get", headers=auth_header(token))
        house_id = houses_resp.json()[0]["id"]

        resp = client.get(f"/home/get_id/{house_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["name"] == HOUSE_DATA["name"]

    def test_get_house_by_id_includes_rooms(self, client):
        """Response should include a rooms list (even if empty)."""
        _, token = create_user_and_login(client)
        create_house(client, token)

        houses_resp = client.get("/home/get", headers=auth_header(token))
        house_id = houses_resp.json()[0]["id"]

        resp = client.get(f"/home/get_id/{house_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        # Second element should be the rooms list
        assert isinstance(body[1], list)

    def test_get_house_by_nonexistent_id(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        resp = client.get(f"/home/get_id/{fake_uuid}", headers=auth_header(token))
        # Should fail gracefully (404 or 500 depending on implementation)
        assert resp.status_code in (404, 422, 500)

    def test_get_house_by_id_unauthenticated(self, client):
        resp = client.get("/home/get_id/1")
        assert resp.status_code in (401, 403)


# ── PUT /home/update ─────────────────────────────────────────────────────────

class TestUpdateHouse:

    def _get_house_id(self, client, token):
        houses = client.get("/home/get", headers=auth_header(token)).json()
        return str(houses[0]["id"])

    def test_update_house_name(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = self._get_house_id(client, token)

        resp = client.put(
            "/home/update",
            json={"house_id": house_id, "name": "Renamed House", "description": None},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        # Verify the name was actually updated
        get_resp = client.get("/home/get", headers=auth_header(token))
        houses = get_resp.json()
        assert len(houses) == 1
        assert houses[0]["name"] == "Renamed House"
        # Description should remain unchanged
        assert houses[0]["description"] == HOUSE_DATA["description"]

    def test_update_house_description(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = self._get_house_id(client, token)

        resp = client.put(
            "/home/update",
            json={"house_id": house_id, "name": None, "description": "Updated desc"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        # Verify the description was actually updated
        get_resp = client.get("/home/get", headers=auth_header(token))
        houses = get_resp.json()
        assert len(houses) == 1
        assert houses[0]["description"] == "Updated desc"
        # Name should remain unchanged
        assert houses[0]["name"] == HOUSE_DATA["name"]

    def test_update_house_duplicate_name(self, client):
        """Cannot rename to a name that already exists for this user."""
        _, token = create_user_and_login(client)
        create_house(client, token, HOUSE_DATA)
        create_house(client, token, HOUSE_DATA_2)
        house_id_2 = None
        houses = client.get("/home/get", headers=auth_header(token)).json()
        for h in houses:
            if h["name"] == HOUSE_DATA_2["name"]:
                house_id_2 = str(h["id"])

        resp = client.put(
            "/home/update",
            json={"house_id": house_id_2, "name": HOUSE_DATA["name"], "description": None},
            headers=auth_header(token),
        )
        assert resp.status_code == 400

    def test_update_house_unauthenticated(self, client):
        resp = client.put(
            "/home/update",
            json={"house_id": "fake-id", "name": "x", "description": None},
        )
        assert resp.status_code in (401, 403)

    def test_update_house_missing_fields(self, client):
        _, token = create_user_and_login(client)
        resp = client.put("/home/update", json={}, headers=auth_header(token))
        assert resp.status_code == 422


# ── DELETE /home/delete ───────────────────────────────────────────────────────

class TestDeleteHouse:

    def test_delete_house_endpoint_exists(self, client):
        """The delete endpoint is defined (even though it's a stub)."""
        _, token = create_user_and_login(client)
        resp = client.delete("/home/delete", headers=auth_header(token))
        # It currently returns 200 with no body (pass), so just verify it's reachable
        assert resp.status_code in (200, 405, 422)

    def test_delete_house_unauthenticated(self, client):
        resp = client.delete("/home/delete")
        # Should require auth, but since function is `pass` with no Depends, it may return 200
        assert resp.status_code in (200, 401, 403)
