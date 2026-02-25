"""Tests for house endpoints (/home/*)."""

import pytest
from uuid import uuid4
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


def get_all_houses(client, token):
    """Get all houses for the current user."""
    resp = client.get("/home/get", headers=auth_header(token))
    return resp.json()


def get_house_id(client, token, name=None):
    """Get the ID of a house by name (defaults to first house)."""
    houses = get_all_houses(client, token)
    if name:
        for h in houses:
            if h["name"] == name:
                return str(h["id"])
    return str(houses[0]["id"]) if houses else None


# ── POST /home/create ────────────────────────────────────────────────────────

class TestCreateHouse:

    def test_create_house_success(self, client):
        _, token = create_user_and_login(client)
        resp = create_house(client, token)
        assert resp.status_code == 200

        # Verify the house was actually stored with the correct data
        houses = get_all_houses(client, token)
        assert len(houses) == 1
        assert houses[0]["name"] == HOUSE_DATA["name"]
        assert houses[0]["description"] == HOUSE_DATA["description"]

    def test_create_house_without_description(self, client):
        _, token = create_user_and_login(client)
        resp = create_house(client, token, {"name": "Simple House"})
        assert resp.status_code == 200

        houses = get_all_houses(client, token)
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
        assert resp.status_code == 200

    def test_create_house_unauthenticated(self, client):
        resp = client.post("/home/create", json=HOUSE_DATA)
        assert resp.status_code in (401, 403)

    def test_create_house_missing_name(self, client):
        _, token = create_user_and_login(client)
        resp = client.post("/home/create", json={}, headers=auth_header(token))
        assert resp.status_code == 422

    def test_create_multiple_houses(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token, HOUSE_DATA)
        create_house(client, token, HOUSE_DATA_2)

        houses = get_all_houses(client, token)
        assert len(houses) == 2
        names = {h["name"] for h in houses}
        assert names == {HOUSE_DATA["name"], HOUSE_DATA_2["name"]}


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

        houses = get_all_houses(client, token)
        assert len(houses) == 2
        names = {h["name"] for h in houses}
        assert "My House" in names
        assert "Beach House" in names
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

        houses = get_all_houses(client, token2)
        assert len(houses) == 1
        assert houses[0]["name"] == "Beach House"
        assert all(h["name"] != HOUSE_DATA["name"] for h in houses)

    def test_get_houses_unauthenticated(self, client):
        resp = client.get("/home/get")
        assert resp.status_code in (401, 403)


# ── GET /home/get_id/{house_id} ──────────────────────────────────────────────

class TestGetHouseById:

    def test_get_house_by_id_success(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.get(f"/home/get_id/{house_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == HOUSE_DATA["name"]
        assert body["description"] == HOUSE_DATA["description"]
        assert body["id"] == house_id

    def test_get_house_by_id_includes_rooms(self, client):
        """Response should include a rooms list (even if empty)."""
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.get(f"/home/get_id/{house_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "rooms" in body
        assert isinstance(body["rooms"], list)

    def test_get_house_by_id_not_found(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = str(uuid4())
        resp = client.get(f"/home/get_id/{fake_uuid}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_get_house_by_id_belongs_to_another_user(self, client):
        """Cannot view a house owned by another user."""
        _, token1 = create_user_and_login(client, TEST_USER)
        create_house(client, token1)
        house_id = get_house_id(client, token1)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.get(f"/home/get_id/{house_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_get_house_by_id_invalid_uuid(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/home/get_id/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_get_house_by_id_unauthenticated(self, client):
        fake_uuid = str(uuid4())
        resp = client.get(f"/home/get_id/{fake_uuid}")
        assert resp.status_code in (401, 403)


# ── PUT /home/update ─────────────────────────────────────────────────────────

class TestUpdateHouse:

    def test_update_house_name(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.put(
            "/home/update",
            json={"house_id": house_id, "name": "Renamed House"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        houses = get_all_houses(client, token)
        assert len(houses) == 1
        assert houses[0]["name"] == "Renamed House"
        # Description should remain unchanged
        assert houses[0]["description"] == HOUSE_DATA["description"]

    def test_update_house_description(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.put(
            "/home/update",
            json={"house_id": house_id, "description": "Updated desc"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        houses = get_all_houses(client, token)
        assert len(houses) == 1
        assert houses[0]["description"] == "Updated desc"
        assert houses[0]["name"] == HOUSE_DATA["name"]

    def test_update_house_name_and_description(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.put(
            "/home/update",
            json={"house_id": house_id, "name": "New Name", "description": "New desc"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        houses = get_all_houses(client, token)
        assert houses[0]["name"] == "New Name"
        assert houses[0]["description"] == "New desc"

    def test_update_house_no_changes(self, client):
        """Sending only house_id with no fields to update should succeed (no-op)."""
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.put(
            "/home/update",
            json={"house_id": house_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

    def test_update_house_duplicate_name(self, client):
        """Cannot rename to a name that already exists for this user."""
        _, token = create_user_and_login(client)
        create_house(client, token, HOUSE_DATA)
        create_house(client, token, HOUSE_DATA_2)
        house_id_2 = get_house_id(client, token, HOUSE_DATA_2["name"])

        resp = client.put(
            "/home/update",
            json={"house_id": house_id_2, "name": HOUSE_DATA["name"]},
            headers=auth_header(token),
        )
        assert resp.status_code == 400
        assert "already have a house" in resp.json()["detail"].lower()

    def test_update_house_same_name_as_self(self, client):
        """Renaming to the same name should succeed (no conflict with self)."""
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.put(
            "/home/update",
            json={"house_id": house_id, "name": HOUSE_DATA["name"]},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

    def test_update_house_not_found(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = str(uuid4())
        resp = client.put(
            "/home/update",
            json={"house_id": fake_uuid, "name": "Ghost"},
            headers=auth_header(token),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_update_house_belongs_to_another_user(self, client):
        """Cannot update a house owned by another user."""
        _, token1 = create_user_and_login(client, TEST_USER)
        create_house(client, token1)
        house_id = get_house_id(client, token1)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.put(
            "/home/update",
            json={"house_id": house_id, "name": "Hacked"},
            headers=auth_header(token2),
        )
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_update_house_unauthenticated(self, client):
        fake_uuid = str(uuid4())
        resp = client.put(
            "/home/update",
            json={"house_id": fake_uuid, "name": "x"},
        )
        assert resp.status_code in (401, 403)

    def test_update_house_missing_house_id(self, client):
        _, token = create_user_and_login(client)
        resp = client.put("/home/update", json={}, headers=auth_header(token))
        assert resp.status_code == 422


# ── DELETE /home/delete/{house_id} ────────────────────────────────────────────

class TestDeleteHouse:

    def test_delete_house_success(self, client):
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp = client.delete(f"/home/delete/{house_id}", headers=auth_header(token))
        assert resp.status_code == 200

        # Verify the house was removed
        houses = get_all_houses(client, token)
        assert len(houses) == 0

    def test_delete_house_verify_gone_by_id(self, client):
        """After deletion, fetching by ID returns 404."""
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        client.delete(f"/home/delete/{house_id}", headers=auth_header(token))

        resp = client.get(f"/home/get_id/{house_id}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_delete_house_not_found(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = str(uuid4())
        resp = client.delete(f"/home/delete/{fake_uuid}", headers=auth_header(token))
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_house_belongs_to_another_user(self, client):
        """Cannot delete a house owned by another user."""
        _, token1 = create_user_and_login(client, TEST_USER)
        create_house(client, token1)
        house_id = get_house_id(client, token1)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.delete(f"/home/delete/{house_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

        # Verify the house still exists for user 1
        houses = get_all_houses(client, token1)
        assert len(houses) == 1

    def test_delete_house_unauthenticated(self, client):
        fake_uuid = str(uuid4())
        resp = client.delete(f"/home/delete/{fake_uuid}")
        assert resp.status_code in (401, 403)

    def test_delete_house_invalid_uuid(self, client):
        _, token = create_user_and_login(client)
        resp = client.delete("/home/delete/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_delete_one_house_others_remain(self, client):
        """Deleting one house should not affect other houses."""
        _, token = create_user_and_login(client)
        create_house(client, token, HOUSE_DATA)
        create_house(client, token, HOUSE_DATA_2)

        house_id = get_house_id(client, token, HOUSE_DATA["name"])
        client.delete(f"/home/delete/{house_id}", headers=auth_header(token))

        remaining = get_all_houses(client, token)
        assert len(remaining) == 1
        assert remaining[0]["name"] == HOUSE_DATA_2["name"]

    def test_delete_house_twice(self, client):
        """Deleting the same house twice should fail the second time."""
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        resp1 = client.delete(f"/home/delete/{house_id}", headers=auth_header(token))
        assert resp1.status_code == 200

        resp2 = client.delete(f"/home/delete/{house_id}", headers=auth_header(token))
        assert resp2.status_code == 404

    def test_delete_house_can_recreate_same_name(self, client):
        """After deleting a house, should be able to create one with the same name."""
        _, token = create_user_and_login(client)
        create_house(client, token)
        house_id = get_house_id(client, token)

        client.delete(f"/home/delete/{house_id}", headers=auth_header(token))
        resp = create_house(client, token)
        assert resp.status_code == 200
