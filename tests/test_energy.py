"""Tests for energy endpoints (/energy/*)."""

from uuid import UUID

from database.enums import DeviceType
from database.models import EnergyHistory
from tests.conftest import (
    TEST_USER,
    TEST_USER_2,
    auth_header,
    create_test_user,
    create_user_and_login,
    get_auth_token,
)


def create_house(client, token, data=None):
    payload = data or {"name": "Energy House", "description": "Energy tests"}
    response = client.post("/home/create", json=payload, headers=auth_header(token))
    assert response.status_code == 200

    houses = client.get("/home/get", headers=auth_header(token)).json()["houses"]
    for house in houses:
        if house["name"] == payload["name"]:
            return house["id"]

    raise AssertionError("House was not created")


def create_room(client, token, house_id, room_name="Energy Room"):
    response = client.post(
        "/rooms/create",
        json={
            "name": room_name,
            "floor": "Entrance",
            "room_type": "other",
            "house_id": house_id,
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200

    rooms = client.get(f"/rooms/get_by_house_id/{house_id}", headers=auth_header(token)).json()["rooms"]
    for room in rooms:
        if room["name"] == room_name:
            return room["id"]

    raise AssertionError("Room was not created")


def create_device(client, token, room_id, name="Energy Light", device_type=DeviceType.LIGHT.value):
    response = client.post(
        "/devices/create",
        json={"name": name, "device_type": device_type, "room_id": room_id},
        headers=auth_header(token),
    )
    assert response.status_code == 200

    devices = client.get("/devices/get", headers=auth_header(token)).json()
    for device in devices:
        if device["name"] == name:
            return device["id"]

    raise AssertionError("Device was not created")


def test_household_energy_records_hourly_snapshot_and_returns_history(client, db_session):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room(client, token, house_id)
    device_id = create_device(client, token, room_id, name="Living Light", device_type=DeviceType.LIGHT.value)

    update_response = client.put(
        "/devices/update",
        json={"device_id": device_id, "parameters": {"status": True}},
        headers=auth_header(token),
    )
    assert update_response.status_code == 200

    household_response = client.get(f"/energy/household/{house_id}", headers=auth_header(token))
    assert household_response.status_code == 200
    household_body = household_response.json()

    assert household_body["total_devices"] == 1
    assert household_body["active_devices"] == 1
    assert household_body["total_estimated_watts"] == 10

    history_response = client.get(f"/energy/household/{house_id}/history?hours=1", headers=auth_header(token))
    assert history_response.status_code == 200
    history = history_response.json()["history"]

    assert len(history) == 1
    assert history[0]["total_estimated_watts"] == 10
    assert history[0]["active_devices"] == 1
    assert history[0]["total_devices"] == 1
    assert history[0]["hour_slot"].endswith("Z")


def test_household_energy_history_upserts_same_hour(client, db_session):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room(client, token, house_id)
    device_id = create_device(client, token, room_id, name="Kitchen Light", device_type=DeviceType.LIGHT.value)

    first_response = client.get(f"/energy/household/{house_id}", headers=auth_header(token))
    assert first_response.status_code == 200
    assert first_response.json()["total_estimated_watts"] == 0

    update_response = client.put(
        "/devices/update",
        json={"device_id": device_id, "parameters": {"status": True}},
        headers=auth_header(token),
    )
    assert update_response.status_code == 200

    second_response = client.get(f"/energy/household/{house_id}", headers=auth_header(token))
    assert second_response.status_code == 200
    assert second_response.json()["total_estimated_watts"] == 10

    history_records = (
        db_session.query(EnergyHistory)
        .filter(EnergyHistory.house_id == UUID(house_id))
        .all()
    )
    assert len(history_records) == 1
    assert history_records[0].total_estimated_watts == 10


def test_household_energy_history_is_user_scoped(client):
    _, token_1 = create_user_and_login(client, TEST_USER)
    house_id = create_house(client, token_1, data={"name": "Private House", "description": "owner 1"})

    create_test_user(client, TEST_USER_2)
    token_2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

    forbidden_response = client.get(f"/energy/household/{house_id}/history?hours=24", headers=auth_header(token_2))
    assert forbidden_response.status_code == 403


def test_room_energy_history_records_and_returns_history(client, db_session):
    from uuid import UUID
    from database.models import RoomEnergyHistory

    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room(client, token, house_id, room_name="Living Room")
    device_id = create_device(client, token, room_id, name="Living Light", device_type=DeviceType.LIGHT.value)

    update_response = client.put(
        "/devices/update",
        json={"device_id": device_id, "parameters": {"status": True}},
        headers=auth_header(token),
    )
    assert update_response.status_code == 200

    history_response = client.get(f"/energy/room/{room_id}/history?hours=1", headers=auth_header(token))
    assert history_response.status_code == 200
    body = history_response.json()

    assert body["room_id"] == room_id
    assert len(body["history"]) == 1
    assert body["history"][0]["total_estimated_watts"] == 10
    assert body["history"][0]["active_devices"] == 1
    assert "summary" in body
    assert "total_kwh" in body["summary"]
    assert "estimated_cost" in body["summary"]

    records = (
        db_session.query(RoomEnergyHistory)
        .filter(RoomEnergyHistory.room_id == UUID(room_id))
        .all()
    )
    assert len(records) == 1
    assert records[0].total_estimated_watts == 10


def test_device_energy_history_records_and_returns_history(client, db_session):
    from uuid import UUID
    from database.models import DeviceEnergyHistory

    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room(client, token, house_id)
    device_id = create_device(client, token, room_id, name="Bedroom Light", device_type=DeviceType.LIGHT.value)

    update_response = client.put(
        "/devices/update",
        json={"device_id": device_id, "parameters": {"status": True}},
        headers=auth_header(token),
    )
    assert update_response.status_code == 200

    history_response = client.get(f"/energy/device/{device_id}/history?hours=1", headers=auth_header(token))
    assert history_response.status_code == 200
    body = history_response.json()

    assert body["device_id"] == device_id
    assert len(body["history"]) == 1
    assert body["history"][0]["estimated_watts"] == 10
    assert body["history"][0]["is_on"] is True
    assert "summary" in body
    assert "total_kwh" in body["summary"]

    records = (
        db_session.query(DeviceEnergyHistory)
        .filter(DeviceEnergyHistory.device_id == UUID(device_id))
        .all()
    )
    assert len(records) == 1
    assert records[0].estimated_watts == 10
    assert records[0].is_on is True


def test_room_energy_history_is_user_scoped(client):
    _, token_1 = create_user_and_login(client, TEST_USER)
    house_id = create_house(client, token_1)
    room_id = create_room(client, token_1, house_id, room_name="Private Room")

    create_test_user(client, TEST_USER_2)
    token_2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

    forbidden_response = client.get(f"/energy/room/{room_id}/history?hours=24", headers=auth_header(token_2))
    assert forbidden_response.status_code == 403


def test_device_energy_history_is_user_scoped(client):
    _, token_1 = create_user_and_login(client, TEST_USER)
    house_id = create_house(client, token_1)
    room_id = create_room(client, token_1, house_id)
    device_id = create_device(client, token_1, room_id, name="Private Device")

    create_test_user(client, TEST_USER_2)
    token_2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

    forbidden_response = client.get(f"/energy/device/{device_id}/history?hours=24", headers=auth_header(token_2))
    assert forbidden_response.status_code == 403


def test_energy_history_includes_cost_summary(client):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room(client, token, house_id)
    create_device(client, token, room_id, name="Cost Light", device_type=DeviceType.LIGHT.value)

    history_response = client.get(f"/energy/household/{house_id}/history?hours=24", headers=auth_header(token))
    assert history_response.status_code == 200
    body = history_response.json()

    assert "summary" in body
    summary = body["summary"]
    assert "total_kwh" in summary
    assert "estimated_cost" in summary
    assert "rate_per_kwh" in summary
    assert summary["currency"] == "USD"
    assert isinstance(summary["total_kwh"], float)
    assert isinstance(summary["estimated_cost"], float)
