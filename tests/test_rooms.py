"""Tests for room endpoints (/rooms/*)."""

import pytest
from database.enums import FloorType
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

HOUSE_DATA = {"name": "Test House", "description": "House for room tests"}
ROOM_DATA = {"name": "Living Room", "floor": FloorType.FLOOR_1.value}
ROOM_DATA_2 = {"name": "Bedroom", "floor": FloorType.FLOOR_2.value}


def create_house(client, token, data=None):
    """Create a house via the API and return its ID."""
    payload = data or HOUSE_DATA.copy()
    client.post("/home/create", json=payload, headers=auth_header(token))
    resp = client.get("/home/get", headers=auth_header(token)).json()
    houses = resp["houses"] if isinstance(resp, dict) and "houses" in resp else resp
    for h in houses:
        if h["name"] == payload["name"]:
            return str(h["id"])
    return None


def create_room(client, token, house_id, data=None):
    """Create a room via the API."""
    payload = data or ROOM_DATA.copy()
    payload["house_id"] = house_id
    return client.post("/rooms/create", json=payload, headers=auth_header(token))


def get_rooms_from_house(client, token, house_id):
    """Get all rooms from a house."""
    resp = client.get(f"/rooms/get_by_house_id/{house_id}", headers=auth_header(token))
    body = resp.json()
    if isinstance(body, dict) and "rooms" in body:
        return body["rooms"]
    return body if isinstance(body, list) else []


def get_room_id(client, token, house_id, name=None):
    """Get the ID of a room by name (defaults to first room)."""
    rooms = get_rooms_from_house(client, token, house_id)
    if name:
        for r in rooms:
            if r["name"] == name:
                return str(r["id"])
    return str(rooms[0]["id"]) if rooms else None


def setup_house(client, user_data=None):
    """Helper: create user, login, create house. Returns (token, house_id)."""
    _, token = create_user_and_login(client, user_data)
    house_id = create_house(client, token)
    return token, house_id


# ── POST /rooms/create ───────────────────────────────────────────────────────

class TestCreateRoom:

    def test_create_room_success(self, client):
        token, house_id = setup_house(client)
        resp = create_room(client, token, house_id)
        assert resp.status_code == 200
        assert "created successfully" in resp.json()["message"].lower()

        rooms = get_rooms_from_house(client, token, house_id)
        assert len(rooms) == 1
        assert rooms[0]["name"] == ROOM_DATA["name"]
        assert rooms[0]["floor"] == ROOM_DATA["floor"]

    def test_create_room_different_floors(self, client):
        token, house_id = setup_house(client)
        for floor in FloorType:
            data = {"name": f"Room {floor.value}", "floor": floor.value}
            resp = create_room(client, token, house_id, data)
            assert resp.status_code == 200

        rooms = get_rooms_from_house(client, token, house_id)
        assert len(rooms) == len(FloorType)

    def test_create_room_duplicate_name_same_house(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        resp = create_room(client, token, house_id)  # same name
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_create_room_same_name_different_houses(self, client):
        """Same room name in different houses should be allowed."""
        token, house_id_1 = setup_house(client)
        house_id_2 = create_house(client, token, {"name": "Second House", "description": "Another"})

        resp1 = create_room(client, token, house_id_1)
        resp2 = create_room(client, token, house_id_2)
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_create_room_nonexistent_house(self, client):
        _, token = create_user_and_login(client)
        fake_house_id = str(uuid4())
        payload = {**ROOM_DATA, "house_id": fake_house_id}
        resp = client.post("/rooms/create", json=payload, headers=auth_header(token))
        assert resp.status_code == 404
        assert "house not found" in resp.json()["detail"].lower()

    def test_create_room_house_belongs_to_another_user(self, client):
        """Cannot create a room in a house owned by another user."""
        token1, house_id = setup_house(client, TEST_USER)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        payload = {**ROOM_DATA, "house_id": house_id}
        resp = client.post("/rooms/create", json=payload, headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_create_room_unauthenticated(self, client):
        resp = client.post(
            "/rooms/create",
            json={**ROOM_DATA, "house_id": str(uuid4())},
        )
        assert resp.status_code in (401, 403)

    def test_create_room_missing_name(self, client):
        token, house_id = setup_house(client)
        resp = client.post(
            "/rooms/create",
            json={"floor": FloorType.FLOOR_1.value, "house_id": house_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_room_missing_floor(self, client):
        token, house_id = setup_house(client)
        resp = client.post(
            "/rooms/create",
            json={"name": "Kitchen", "house_id": house_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_room_missing_house_id(self, client):
        _, token = create_user_and_login(client)
        resp = client.post(
            "/rooms/create",
            json={"name": "Kitchen", "floor": FloorType.FLOOR_1.value},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_room_invalid_floor(self, client):
        token, house_id = setup_house(client)
        resp = client.post(
            "/rooms/create",
            json={"name": "Kitchen", "floor": "99th", "house_id": house_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_multiple_rooms(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id, ROOM_DATA)
        create_room(client, token, house_id, ROOM_DATA_2)

        rooms = get_rooms_from_house(client, token, house_id)
        assert len(rooms) == 2
        names = {r["name"] for r in rooms}
        assert names == {ROOM_DATA["name"], ROOM_DATA_2["name"]}


# ── GET /rooms/get_by_house_id/{house_id} ─────────────────────────────────────

class TestGetRoomsFromHouse:

    def test_get_rooms_empty(self, client):
        token, house_id = setup_house(client)
        resp = client.get(f"/rooms/get_by_house_id/{house_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        rooms = body["rooms"] if isinstance(body, dict) and "rooms" in body else body
        assert rooms == []

    def test_get_rooms_returns_created(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id, ROOM_DATA)
        create_room(client, token, house_id, ROOM_DATA_2)

        rooms = get_rooms_from_house(client, token, house_id)
        assert len(rooms) == 2
        names = {r["name"] for r in rooms}
        assert ROOM_DATA["name"] in names
        assert ROOM_DATA_2["name"] in names

    def test_get_rooms_only_from_specified_house(self, client):
        """Rooms from one house should not appear in another."""
        token, house_id_1 = setup_house(client)
        house_id_2 = create_house(client, token, {"name": "Other House", "description": "Other"})

        create_room(client, token, house_id_1, ROOM_DATA)
        create_room(client, token, house_id_2, ROOM_DATA_2)

        rooms_1 = get_rooms_from_house(client, token, house_id_1)
        assert len(rooms_1) == 1
        assert rooms_1[0]["name"] == ROOM_DATA["name"]

        rooms_2 = get_rooms_from_house(client, token, house_id_2)
        assert len(rooms_2) == 1
        assert rooms_2[0]["name"] == ROOM_DATA_2["name"]

    def test_get_rooms_nonexistent_house(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = str(uuid4())
        resp = client.get(f"/rooms/get_by_house_id/{fake_uuid}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_get_rooms_house_belongs_to_another_user(self, client):
        """Cannot list rooms from a house owned by another user."""
        token1, house_id = setup_house(client, TEST_USER)
        create_room(client, token1, house_id)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.get(f"/rooms/get_by_house_id/{house_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_get_rooms_unauthenticated(self, client):
        fake_uuid = str(uuid4())
        resp = client.get(f"/rooms/get_by_house_id/{fake_uuid}")
        assert resp.status_code in (401, 403)

    def test_get_rooms_invalid_uuid(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/rooms/get_by_house_id/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422


# ── GET /rooms/get_by_room_id/{room_id} ──────────────────────────────────────

class TestGetRoomById:

    def test_get_room_by_id_success(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.get(f"/rooms/get_by_room_id/{room_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()["room"]
        assert body["name"] == ROOM_DATA["name"]
        assert body["floor"] == ROOM_DATA["floor"]
        assert body["id"] == room_id
        assert body["house_id"] == house_id

    def test_get_room_by_id_includes_devices(self, client):
        """Response should include a devices list (even if empty)."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.get(f"/rooms/get_by_room_id/{room_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()["room"]
        assert "devices" in body
        assert isinstance(body["devices"], list)

    def test_get_room_by_id_not_found(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = str(uuid4())
        resp = client.get(f"/rooms/get_by_room_id/{fake_uuid}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_get_room_by_id_belongs_to_another_user(self, client):
        """Cannot view a room owned by another user."""
        token1, house_id = setup_house(client, TEST_USER)
        create_room(client, token1, house_id)
        room_id = get_room_id(client, token1, house_id)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.get(f"/rooms/get_by_room_id/{room_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_get_room_by_id_invalid_uuid(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/rooms/get_by_room_id/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_get_room_by_id_unauthenticated(self, client):
        fake_uuid = str(uuid4())
        resp = client.get(f"/rooms/get_by_room_id/{fake_uuid}")
        assert resp.status_code in (401, 403)


# ── PUT /rooms/update ────────────────────────────────────────────────────────

class TestUpdateRoom:

    def test_update_room_name(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id, "name": "Kitchen"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        assert "updated successfully" in resp.json()["message"].lower()

        rooms = get_rooms_from_house(client, token, house_id)
        assert rooms[0]["name"] == "Kitchen"
        # Floor should remain unchanged
        assert rooms[0]["floor"] == ROOM_DATA["floor"]

    def test_update_room_floor(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id, "floor": FloorType.FLOOR_3.value},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        rooms = get_rooms_from_house(client, token, house_id)
        assert rooms[0]["floor"] == FloorType.FLOOR_3.value
        assert rooms[0]["name"] == ROOM_DATA["name"]

    def test_update_room_name_and_floor(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id, "name": "Office", "floor": FloorType.FLOOR_2.value},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        rooms = get_rooms_from_house(client, token, house_id)
        assert rooms[0]["name"] == "Office"
        assert rooms[0]["floor"] == FloorType.FLOOR_2.value

    def test_update_room_no_changes(self, client):
        """Sending only room_id with no fields to update should succeed (no-op)."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

    def test_update_room_duplicate_name(self, client):
        """Cannot rename to a name that already exists in the same house."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id, ROOM_DATA)
        create_room(client, token, house_id, ROOM_DATA_2)
        room_id_2 = get_room_id(client, token, house_id, ROOM_DATA_2["name"])

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id_2, "name": ROOM_DATA["name"]},
            headers=auth_header(token),
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_update_room_same_name_as_self(self, client):
        """Renaming to the same name should succeed (no conflict with self)."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id, "name": ROOM_DATA["name"]},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

    def test_update_room_not_found(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = str(uuid4())
        resp = client.put(
            "/rooms/update",
            json={"room_id": fake_uuid, "name": "Ghost"},
            headers=auth_header(token),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_update_room_belongs_to_another_user(self, client):
        """Cannot update a room owned by another user."""
        token1, house_id = setup_house(client, TEST_USER)
        create_room(client, token1, house_id)
        room_id = get_room_id(client, token1, house_id)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id, "name": "Hacked"},
            headers=auth_header(token2),
        )
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_update_room_unauthenticated(self, client):
        fake_uuid = str(uuid4())
        resp = client.put(
            "/rooms/update",
            json={"room_id": fake_uuid, "name": "x"},
        )
        assert resp.status_code in (401, 403)

    def test_update_room_missing_room_id(self, client):
        _, token = create_user_and_login(client)
        resp = client.put("/rooms/update", json={}, headers=auth_header(token))
        assert resp.status_code == 422

    def test_update_room_invalid_floor(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.put(
            "/rooms/update",
            json={"room_id": room_id, "floor": "99th"},
            headers=auth_header(token),
        )
        assert resp.status_code == 422


# ── DELETE /rooms/delete/{room_id} ────────────────────────────────────────────

class TestDeleteRoom:

    def test_delete_room_success(self, client):
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp = client.delete(f"/rooms/delete/{room_id}", headers=auth_header(token))
        assert resp.status_code == 200
        assert "deleted successfully" in resp.json()["message"].lower()

        rooms = get_rooms_from_house(client, token, house_id)
        assert len(rooms) == 0

    def test_delete_room_verify_gone_by_id(self, client):
        """After deletion, fetching by ID returns 404."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        client.delete(f"/rooms/delete/{room_id}", headers=auth_header(token))

        resp = client.get(f"/rooms/get_by_room_id/{room_id}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_delete_room_not_found(self, client):
        _, token = create_user_and_login(client)
        fake_uuid = str(uuid4())
        resp = client.delete(f"/rooms/delete/{fake_uuid}", headers=auth_header(token))
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_room_belongs_to_another_user(self, client):
        """Cannot delete a room owned by another user."""
        token1, house_id = setup_house(client, TEST_USER)
        create_room(client, token1, house_id)
        room_id = get_room_id(client, token1, house_id)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.delete(f"/rooms/delete/{room_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

        # Verify the room still exists for user 1
        rooms = get_rooms_from_house(client, token1, house_id)
        assert len(rooms) == 1

    def test_delete_room_unauthenticated(self, client):
        fake_uuid = str(uuid4())
        resp = client.delete(f"/rooms/delete/{fake_uuid}")
        assert resp.status_code in (401, 403)

    def test_delete_room_invalid_uuid(self, client):
        _, token = create_user_and_login(client)
        resp = client.delete("/rooms/delete/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_delete_one_room_others_remain(self, client):
        """Deleting one room should not affect other rooms."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id, ROOM_DATA)
        create_room(client, token, house_id, ROOM_DATA_2)

        room_id = get_room_id(client, token, house_id, ROOM_DATA["name"])
        client.delete(f"/rooms/delete/{room_id}", headers=auth_header(token))

        remaining = get_rooms_from_house(client, token, house_id)
        assert len(remaining) == 1
        assert remaining[0]["name"] == ROOM_DATA_2["name"]

    def test_delete_room_twice(self, client):
        """Deleting the same room twice should fail the second time."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        resp1 = client.delete(f"/rooms/delete/{room_id}", headers=auth_header(token))
        assert resp1.status_code == 200

        resp2 = client.delete(f"/rooms/delete/{room_id}", headers=auth_header(token))
        assert resp2.status_code == 404

    def test_delete_room_can_recreate_same_name(self, client):
        """After deleting a room, should be able to create one with the same name."""
        token, house_id = setup_house(client)
        create_room(client, token, house_id)
        room_id = get_room_id(client, token, house_id)

        client.delete(f"/rooms/delete/{room_id}", headers=auth_header(token))
        resp = create_room(client, token, house_id)
        assert resp.status_code == 200
