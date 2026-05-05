import pytest
from starlette.websockets import WebSocketDisconnect

from database.enums import AutomationTriggerType, DeviceType, FloorType
from database.models import Room
from tests.conftest import auth_header, create_user_and_login


def create_house(client, token, data=None):
    payload = data or {"name": "Realtime House", "description": "Realtime testing"}
    client.post("/home/create", json=payload, headers=auth_header(token))
    houses = client.get("/home/get", headers=auth_header(token)).json()["houses"]
    for house in houses:
        if house["name"] == payload["name"]:
            return house["id"]
    return None


def create_room_in_db(db_session, house_id, name="Realtime Room", floor=FloorType.FLOOR_1):
    from uuid import UUID

    room = Room(name=name, floor=floor, house_id=UUID(house_id))
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return str(room.id)


def receive_event(websocket, event_name, max_messages=15):
    for _ in range(max_messages):
        message = websocket.receive_json()
        if message.get("event") == event_name:
            return message
    raise AssertionError(f"Expected event '{event_name}' within {max_messages} messages")


def setup_device(client, db_session, device_name="Living Room Light", device_type=DeviceType.LIGHT.value):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id)
    response = client.post(
        "/devices/create",
        json={"name": device_name, "device_type": device_type, "room_id": room_id},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    devices = client.get("/devices/get", headers=auth_header(token)).json()
    return token, house_id, room_id, devices[0]["id"]


def test_realtime_websocket_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/notifications/ws?token=invalid-token"):
            pass


def test_realtime_device_status_changed_event(client, db_session):
    token, _, _, device_id = setup_device(client, db_session)

    with client.websocket_connect(f"/notifications/ws?token={token}") as websocket:
        connected = receive_event(websocket, "connected")
        assert connected["event"] == "connected"

        update_response = client.put(
            "/devices/update",
            json={"device_id": device_id, "parameters": {"status": True}},
            headers=auth_header(token),
        )
        assert update_response.status_code == 200

        event = receive_event(websocket, "deviceStatusChanged")
        assert event["deviceId"] == device_id
        assert event["status"] == "on"
        assert "timestamp" in event


def test_realtime_automation_trigger_event_on_parameter_threshold(client, db_session):
    token, _, _, device_id = setup_device(
        client,
        db_session,
        device_name="Thermostat",
        device_type=DeviceType.THERMOSTAT.value,
    )

    automation_response = client.post(
        "/automations/create",
        json={
            "name": "High Temp Alert",
            "trigger_type": AutomationTriggerType.TEMPERATURE.value,
            "trigger_value": "24",
            "execution_day": None,
            "turn_on": True,
            "device_id": device_id,
        },
        headers=auth_header(token),
    )
    assert automation_response.status_code == 200

    with client.websocket_connect(f"/notifications/ws?token={token}") as websocket:
        receive_event(websocket, "connected")

        update_response = client.put(
            "/devices/update",
            json={"device_id": device_id, "parameters": {"status": True, "temperature": 26}},
            headers=auth_header(token),
        )
        assert update_response.status_code == 200

        event = receive_event(websocket, "automationTriggered")
        assert event["event"] == "automationTriggered"
        assert event["deviceId"] == device_id
        assert event["reason"] == "deviceParameterThreshold"
        assert "timestamp" in event


def test_threshold_automation_executes_device_action(client, db_session):
    token, _, _, device_id = setup_device(
        client,
        db_session,
        device_name="Auto Oven",
        device_type=DeviceType.OVEN.value,
    )

    automation_response = client.post(
        "/automations/create",
        json={
            "name": "Turn On Above Threshold",
            "trigger_type": AutomationTriggerType.TEMPERATURE.value,
            "trigger_value": "24",
            "execution_day": None,
            "turn_on": True,
            "parameters": {"power_setting": 80},
            "device_id": device_id,
        },
        headers=auth_header(token),
    )
    assert automation_response.status_code == 200

    update_response = client.put(
        "/devices/update",
        json={"device_id": device_id, "parameters": {"status": False, "temperature": 26}},
        headers=auth_header(token),
    )
    assert update_response.status_code == 200

    device_response = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token))
    assert device_response.status_code == 200
    parameters = device_response.json()["parameters"]
    assert parameters["status"] is True
    assert parameters["power_setting"] == 80
