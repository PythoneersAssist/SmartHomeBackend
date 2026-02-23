"""Tests for device endpoints (/devices/*)."""

import pytest
from database.models import House, Room, Device
from database.enums import DeviceType, FloorType
from utils import device_parameters
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

HOUSE_DATA = {"name": "Test House", "description": "Test house for devices"}


def create_house(client, token, data=None):
    """Create a house via the API and return its ID."""
    payload = data or HOUSE_DATA.copy()
    client.post("/home/create", json=payload, headers=auth_header(token))
    houses = client.get("/home/get", headers=auth_header(token)).json()
    for h in houses:
        if h["name"] == payload["name"]:
            return h["id"]
    return None


def create_room_in_db(db_session, house_id, name="Living Room", floor=FloorType.FLOOR_1):
    """Create a room directly in the DB (rooms API is not implemented yet)."""
    from uuid import UUID
    room = Room(name=name, floor=floor, house_id=UUID(house_id))
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return str(room.id)


def create_device_via_api(client, token, name, device_type, room_id):
    """Create a device via the API."""
    return client.post(
        "/devices/create",
        json={"name": name, "device_type": device_type, "room_id": room_id},
        headers=auth_header(token),
    )


def setup_house_and_room(client, db_session, user_data=None, room_name="Living Room"):
    """Helper: create user, login, create house, create room. Returns (token, house_id, room_id)."""
    _, token = create_user_and_login(client, user_data)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id, name=room_name)
    return token, house_id, room_id


def get_all_devices(client, token):
    """Get all devices for the current user."""
    resp = client.get("/devices/get", headers=auth_header(token))
    return resp.json()


# ── POST /devices/create ─────────────────────────────────────────────────────

class TestCreateDevice:

    def test_create_device_success(self, client, db_session):
        token, _, room_id = setup_house_and_room(client, db_session)
        resp = create_device_via_api(client, token, "Ceiling Light", DeviceType.LIGHT.value, room_id)
        assert resp.status_code == 200

        # Verify the device was actually stored
        devices = get_all_devices(client, token)
        assert len(devices) == 1
        assert devices[0]["name"] == "Ceiling Light"
        assert devices[0]["type"] == DeviceType.LIGHT.value
        assert devices[0]["room_id"] == room_id

    @pytest.mark.parametrize("name,device_type,expected_params", [
        ("Light", DeviceType.LIGHT.value, device_parameters.DEFAULT_DEVICE),
        ("LED Strip", DeviceType.LED_STRIP.value, device_parameters.LED_DEVICE),
        ("Thermostat", DeviceType.THERMOSTAT.value, device_parameters.THERMOSTAT_DEVICE),
        ("Fan", DeviceType.FANS.value, device_parameters.FAN_DEVICE),
        ("AC", DeviceType.AIR_CONDITIONER.value, device_parameters.AIR_CONDITIONER_DEVICE),
        ("Heater", DeviceType.HEATER.value, device_parameters.HEATER_DEVICE),
        ("TV", DeviceType.TV.value, device_parameters.TV_DEVICE),
        ("Speaker", DeviceType.SPEAKER.value, device_parameters.SPEAKER_DEVICE),
        ("Oven", DeviceType.OVEN.value, device_parameters.OVEN_DEVICE),
        ("Washer", DeviceType.WASHER.value, device_parameters.WASHER_AND_DRIER_DEVICE),
        ("Fridge", DeviceType.REFRIGERATOR.value, device_parameters.REFRIGERATOR_DEVICE),
    ])
    def test_create_device_assigns_default_parameters(self, client, db_session, name, device_type, expected_params):
        """Each device type should receive its correct default parameters."""
        token, _, room_id = setup_house_and_room(client, db_session)
        create_device_via_api(client, token, name, device_type, room_id)
        devices = get_all_devices(client, token)
        assert devices[0]["parameters"] == expected_params

    def test_create_device_duplicate_name_same_room(self, client, db_session):
        token, _, room_id = setup_house_and_room(client, db_session)
        create_device_via_api(client, token, "Light", DeviceType.LIGHT.value, room_id)
        resp = create_device_via_api(client, token, "Light", DeviceType.LIGHT.value, room_id)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_create_device_same_name_different_rooms(self, client, db_session):
        """Same device name in different rooms should be allowed."""
        token, house_id, room_id_1 = setup_house_and_room(client, db_session)
        room_id_2 = create_room_in_db(db_session, house_id, name="Bedroom")

        resp1 = create_device_via_api(client, token, "Light", DeviceType.LIGHT.value, room_id_1)
        resp2 = create_device_via_api(client, token, "Light", DeviceType.LIGHT.value, room_id_2)
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        devices = get_all_devices(client, token)
        assert len(devices) == 2

    def test_create_device_same_name_different_type_same_room(self, client, db_session):
        """Same name but different type in same room should still fail (name must be unique per room)."""
        token, _, room_id = setup_house_and_room(client, db_session)
        create_device_via_api(client, token, "MyDevice", DeviceType.LIGHT.value, room_id)
        resp = create_device_via_api(client, token, "MyDevice", DeviceType.OUTLET.value, room_id)
        assert resp.status_code == 400

    def test_create_device_nonexistent_room(self, client, db_session):
        _, token = create_user_and_login(client)
        fake_room_id = str(uuid4())
        resp = create_device_via_api(client, token, "Light", DeviceType.LIGHT.value, fake_room_id)
        assert resp.status_code == 404
        assert "room not found" in resp.json()["detail"].lower()

    def test_create_device_room_belongs_to_another_user(self, client, db_session):
        """Cannot create a device in a room owned by another user."""
        # User 1 creates house and room
        token1, house_id, room_id = setup_house_and_room(client, db_session, TEST_USER)

        # User 2 tries to create device in user 1's room
        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = create_device_via_api(client, token2, "Hacked Light", DeviceType.LIGHT.value, room_id)
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_create_device_unauthenticated(self, client, db_session):
        resp = client.post(
            "/devices/create",
            json={"name": "Light", "device_type": DeviceType.LIGHT.value, "room_id": str(uuid4())},
        )
        assert resp.status_code in (401, 403)

    def test_create_device_missing_name(self, client, db_session):
        token, _, room_id = setup_house_and_room(client, db_session)
        resp = client.post(
            "/devices/create",
            json={"device_type": DeviceType.LIGHT.value, "room_id": room_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_device_missing_type(self, client, db_session):
        token, _, room_id = setup_house_and_room(client, db_session)
        resp = client.post(
            "/devices/create",
            json={"name": "Light", "room_id": room_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_device_missing_room_id(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.post(
            "/devices/create",
            json={"name": "Light", "device_type": DeviceType.LIGHT.value},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_device_invalid_type(self, client, db_session):
        token, _, room_id = setup_house_and_room(client, db_session)
        resp = client.post(
            "/devices/create",
            json={"name": "Light", "device_type": 9999, "room_id": room_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_device_invalid_room_id_format(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.post(
            "/devices/create",
            json={"name": "Light", "device_type": DeviceType.LIGHT.value, "room_id": "not-a-uuid"},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_device_empty_body(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.post("/devices/create", json={}, headers=auth_header(token))
        assert resp.status_code == 422

    def test_create_multiple_devices_in_same_room(self, client, db_session):
        token, _, room_id = setup_house_and_room(client, db_session)
        create_device_via_api(client, token, "Light", DeviceType.LIGHT.value, room_id)
        create_device_via_api(client, token, "Fan", DeviceType.FANS.value, room_id)
        create_device_via_api(client, token, "Outlet", DeviceType.OUTLET.value, room_id)

        devices = get_all_devices(client, token)
        assert len(devices) == 3
        names = {d["name"] for d in devices}
        assert names == {"Light", "Fan", "Outlet"}


# ── GET /devices/get ──────────────────────────────────────────────────────────

class TestGetDevices:

    def test_get_devices_empty(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.get("/devices/get", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_devices_returns_created(self, client, db_session):
        token, _, room_id = setup_house_and_room(client, db_session)
        create_device_via_api(client, token, "Light", DeviceType.LIGHT.value, room_id)
        create_device_via_api(client, token, "Fan", DeviceType.FANS.value, room_id)

        resp = client.get("/devices/get", headers=auth_header(token))
        assert resp.status_code == 200
        devices = resp.json()
        assert len(devices) == 2
        names = {d["name"] for d in devices}
        assert names == {"Light", "Fan"}

    def test_get_devices_across_multiple_rooms(self, client, db_session):
        token, house_id, room_id_1 = setup_house_and_room(client, db_session, room_name="Room A")
        room_id_2 = create_room_in_db(db_session, house_id, name="Room B")

        create_device_via_api(client, token, "Light A", DeviceType.LIGHT.value, room_id_1)
        create_device_via_api(client, token, "Light B", DeviceType.LIGHT.value, room_id_2)

        devices = get_all_devices(client, token)
        assert len(devices) == 2
        room_ids = {d["room_id"] for d in devices}
        assert room_id_1 in room_ids
        assert room_id_2 in room_ids

    def test_get_devices_across_multiple_houses(self, client, db_session):
        _, token = create_user_and_login(client)
        house_id_1 = create_house(client, token, {"name": "House 1", "description": "H1"})
        house_id_2 = create_house(client, token, {"name": "House 2", "description": "H2"})
        room_id_1 = create_room_in_db(db_session, house_id_1, name="Room H1")
        room_id_2 = create_room_in_db(db_session, house_id_2, name="Room H2")

        create_device_via_api(client, token, "Device H1", DeviceType.LIGHT.value, room_id_1)
        create_device_via_api(client, token, "Device H2", DeviceType.OUTLET.value, room_id_2)

        devices = get_all_devices(client, token)
        assert len(devices) == 2

    def test_get_devices_only_own(self, client, db_session):
        """User should only see devices in their own houses."""
        # User 1 creates a device
        token1, _, room_id_1 = setup_house_and_room(client, db_session, TEST_USER)
        create_device_via_api(client, token1, "User1 Light", DeviceType.LIGHT.value, room_id_1)

        # User 2 creates a device
        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])
        house_id_2 = create_house(client, token2, {"name": "User2 House", "description": "U2"})
        room_id_2 = create_room_in_db(db_session, house_id_2, name="User2 Room")
        create_device_via_api(client, token2, "User2 Fan", DeviceType.FANS.value, room_id_2)

        # User 1 should only see their own device
        devices_1 = get_all_devices(client, token1)
        assert len(devices_1) == 1
        assert devices_1[0]["name"] == "User1 Light"

        # User 2 should only see their own device
        devices_2 = get_all_devices(client, token2)
        assert len(devices_2) == 1
        assert devices_2[0]["name"] == "User2 Fan"

    def test_get_devices_unauthenticated(self, client):
        resp = client.get("/devices/get")
        assert resp.status_code in (401, 403)


# ── GET /devices/get_id/{device_id} ──────────────────────────────────────────

class TestGetDeviceById:

    def _create_and_get_device_id(self, client, db_session, token=None, user_data=None):
        """Helper: setup house+room, create a device, return (token, device_id, room_id)."""
        if token is None:
            token, _, room_id = setup_house_and_room(client, db_session, user_data)
        else:
            house_id = create_house(client, token)
            room_id = create_room_in_db(db_session, house_id)
        create_device_via_api(client, token, "Test Device", DeviceType.LIGHT.value, room_id)
        devices = get_all_devices(client, token)
        return token, devices[0]["id"], room_id

    def test_get_device_by_id_success(self, client, db_session):
        token, device_id, room_id = self._create_and_get_device_id(client, db_session)
        resp = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == device_id
        assert body["name"] == "Test Device"
        assert body["type"] == DeviceType.LIGHT.value
        assert body["room_id"] == room_id
        assert body["parameters"] == device_parameters.DEFAULT_DEVICE

    def test_get_device_by_id_nonexistent(self, client, db_session):
        _, token = create_user_and_login(client)
        fake_id = str(uuid4())
        resp = client.get(f"/devices/get_id/{fake_id}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_get_device_by_id_belongs_to_another_user(self, client, db_session):
        """Cannot view a device owned by another user."""
        # User 1 creates device
        token1, device_id, _ = self._create_and_get_device_id(client, db_session, user_data=TEST_USER)

        # User 2 tries to view it
        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_get_device_by_id_invalid_uuid(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.get("/devices/get_id/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_get_device_by_id_unauthenticated(self, client):
        fake_id = str(uuid4())
        resp = client.get(f"/devices/get_id/{fake_id}")
        assert resp.status_code in (401, 403)


# ── PUT /devices/update ──────────────────────────────────────────────────────

class TestUpdateDevice:

    def _setup_device(self, client, db_session, user_data=None, device_name="Test Device", device_type=DeviceType.LIGHT.value):
        """Helper: create user, house, room, device. Returns (token, device_id, room_id)."""
        token, _, room_id = setup_house_and_room(client, db_session, user_data)
        create_device_via_api(client, token, device_name, device_type, room_id)
        devices = get_all_devices(client, token)
        device_id = devices[0]["id"]
        return token, device_id, room_id

    def test_update_device_name(self, client, db_session):
        token, device_id, _ = self._setup_device(client, db_session)
        resp = client.put(
            "/devices/update",
            json={"device_id": device_id, "name": "Renamed Light"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        # Verify the name was updated
        get_resp = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token))
        assert get_resp.json()["name"] == "Renamed Light"

    def test_update_device_parameters(self, client, db_session):
        token, device_id, _ = self._setup_device(client, db_session)
        new_params = {"status": True}
        resp = client.put(
            "/devices/update",
            json={"device_id": device_id, "parameters": new_params},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        get_resp = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token))
        assert get_resp.json()["parameters"] == new_params

    def test_update_device_name_and_parameters(self, client, db_session):
        token, device_id, _ = self._setup_device(client, db_session)
        new_params = {"status": True}
        resp = client.put(
            "/devices/update",
            json={"device_id": device_id, "name": "New Name", "parameters": new_params},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        get_resp = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token))
        body = get_resp.json()
        assert body["name"] == "New Name"
        assert body["parameters"] == new_params

    def test_update_device_no_changes(self, client, db_session):
        """Sending only device_id with no fields to update should succeed (no-op)."""
        token, device_id, _ = self._setup_device(client, db_session)
        resp = client.put(
            "/devices/update",
            json={"device_id": device_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

    def test_update_device_duplicate_name_same_room(self, client, db_session):
        """Cannot rename a device to a name that already exists in the same room."""
        token, _, room_id = setup_house_and_room(client, db_session)
        create_device_via_api(client, token, "Light A", DeviceType.LIGHT.value, room_id)
        create_device_via_api(client, token, "Light B", DeviceType.OUTLET.value, room_id)

        devices = get_all_devices(client, token)
        device_b_id = next(d["id"] for d in devices if d["name"] == "Light B")

        resp = client.put(
            "/devices/update",
            json={"device_id": device_b_id, "name": "Light A"},
            headers=auth_header(token),
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_update_device_same_name_as_self(self, client, db_session):
        """Renaming to the same name should succeed (no conflict with self)."""
        token, device_id, _ = self._setup_device(client, db_session, device_name="Same Name")
        resp = client.put(
            "/devices/update",
            json={"device_id": device_id, "name": "Same Name"},
            headers=auth_header(token),
        )
        # Should succeed since it's the same device
        assert resp.status_code == 200

    def test_update_device_nonexistent(self, client, db_session):
        _, token = create_user_and_login(client)
        fake_id = str(uuid4())
        resp = client.put(
            "/devices/update",
            json={"device_id": fake_id, "name": "Ghost"},
            headers=auth_header(token),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_update_device_belongs_to_another_user(self, client, db_session):
        """Cannot update a device owned by another user."""
        token1, device_id, _ = self._setup_device(client, db_session, user_data=TEST_USER)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.put(
            "/devices/update",
            json={"device_id": device_id, "name": "Hacked"},
            headers=auth_header(token2),
        )
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_update_device_unauthenticated(self, client):
        fake_id = str(uuid4())
        resp = client.put(
            "/devices/update",
            json={"device_id": fake_id, "name": "Nope"},
        )
        assert resp.status_code in (401, 403)

    def test_update_device_missing_device_id(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.put(
            "/devices/update",
            json={"name": "No ID"},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_update_device_invalid_device_id(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.put(
            "/devices/update",
            json={"device_id": "not-a-uuid", "name": "Bad"},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_update_device_preserves_unchanged_fields(self, client, db_session):
        """Updating only the name should not alter parameters and vice versa."""
        token, device_id, _ = self._setup_device(client, db_session)

        # Get original state
        original = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token)).json()

        # Update only name
        client.put(
            "/devices/update",
            json={"device_id": device_id, "name": "New Name"},
            headers=auth_header(token),
        )
        after_name = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token)).json()
        assert after_name["name"] == "New Name"
        assert after_name["parameters"] == original["parameters"]
        assert after_name["type"] == original["type"]

        # Update only parameters
        new_params = {"status": True}
        client.put(
            "/devices/update",
            json={"device_id": device_id, "parameters": new_params},
            headers=auth_header(token),
        )
        after_params = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token)).json()
        assert after_params["name"] == "New Name"  # preserved from previous update
        assert after_params["parameters"] == new_params
        assert after_params["type"] == original["type"]


# ── DELETE /devices/delete/{device_id} ────────────────────────────────────────

class TestDeleteDevice:

    def _setup_device(self, client, db_session, user_data=None, device_name="Test Device"):
        token, _, room_id = setup_house_and_room(client, db_session, user_data)
        create_device_via_api(client, token, device_name, DeviceType.LIGHT.value, room_id)
        devices = get_all_devices(client, token)
        device_id = devices[0]["id"]
        return token, device_id, room_id

    def test_delete_device_success(self, client, db_session):
        token, device_id, _ = self._setup_device(client, db_session)
        resp = client.delete(f"/devices/delete/{device_id}", headers=auth_header(token))
        assert resp.status_code == 200

        # Verify the device was removed
        devices = get_all_devices(client, token)
        assert len(devices) == 0

    def test_delete_device_verify_gone_by_id(self, client, db_session):
        """After deletion, fetching by ID returns 404."""
        token, device_id, _ = self._setup_device(client, db_session)
        client.delete(f"/devices/delete/{device_id}", headers=auth_header(token))

        resp = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_delete_device_nonexistent(self, client, db_session):
        _, token = create_user_and_login(client)
        fake_id = str(uuid4())
        resp = client.delete(f"/devices/delete/{fake_id}", headers=auth_header(token))
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_device_belongs_to_another_user(self, client, db_session):
        """Cannot delete a device owned by another user."""
        token1, device_id, _ = self._setup_device(client, db_session, user_data=TEST_USER)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.delete(f"/devices/delete/{device_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

        # Verify the device still exists for user 1
        devices = get_all_devices(client, token1)
        assert len(devices) == 1

    def test_delete_device_unauthenticated(self, client):
        fake_id = str(uuid4())
        resp = client.delete(f"/devices/delete/{fake_id}")
        assert resp.status_code in (401, 403)

    def test_delete_device_invalid_uuid(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.delete("/devices/delete/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_delete_one_device_others_remain(self, client, db_session):
        """Deleting one device should not affect other devices."""
        token, _, room_id = setup_house_and_room(client, db_session)
        create_device_via_api(client, token, "Light A", DeviceType.LIGHT.value, room_id)
        create_device_via_api(client, token, "Light B", DeviceType.OUTLET.value, room_id)
        create_device_via_api(client, token, "Light C", DeviceType.FANS.value, room_id)

        devices = get_all_devices(client, token)
        assert len(devices) == 3

        device_b_id = next(d["id"] for d in devices if d["name"] == "Light B")
        client.delete(f"/devices/delete/{device_b_id}", headers=auth_header(token))

        remaining = get_all_devices(client, token)
        assert len(remaining) == 2
        remaining_names = {d["name"] for d in remaining}
        assert "Light B" not in remaining_names
        assert "Light A" in remaining_names
        assert "Light C" in remaining_names

    def test_delete_device_twice(self, client, db_session):
        """Deleting the same device twice should fail the second time."""
        token, device_id, _ = self._setup_device(client, db_session)
        resp1 = client.delete(f"/devices/delete/{device_id}", headers=auth_header(token))
        assert resp1.status_code == 200

        resp2 = client.delete(f"/devices/delete/{device_id}", headers=auth_header(token))
        assert resp2.status_code == 404

    def test_delete_device_can_recreate_same_name(self, client, db_session):
        """After deleting a device, should be able to create one with the same name."""
        token, device_id, room_id = self._setup_device(client, db_session, device_name="Reusable Name")
        client.delete(f"/devices/delete/{device_id}", headers=auth_header(token))

        resp = create_device_via_api(client, token, "Reusable Name", DeviceType.LIGHT.value, room_id)
        assert resp.status_code == 200
