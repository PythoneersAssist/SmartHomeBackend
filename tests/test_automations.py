"""Tests for the automation CRUD endpoints (/automations/*).

The scheduler tests (test_automation_scheduler.py) only exercise
``/automations/create`` as a means to an end. This file covers the actual
REST surface: create validation, listing, fetch-by-id, update, delete, and the
ownership / not-found / validation edge cases for each.
"""

from uuid import uuid4

from database.enums import AutomationTriggerType, DeviceType, FloorType
from database.models import Room
from tests.conftest import (
    TEST_USER,
    TEST_USER_2,
    auth_header,
    create_test_user,
    create_user_and_login,
    get_auth_token,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_house(client, token, name="Automation House"):
    client.post("/home/create", json={"name": name, "description": "x"}, headers=auth_header(token))
    houses = client.get("/home/get", headers=auth_header(token)).json()["houses"]
    return next(h["id"] for h in houses if h["name"] == name)


def create_room_in_db(db_session, house_id, name="Automation Room", floor=FloorType.FLOOR_1):
    from uuid import UUID

    room = Room(name=name, floor=floor, house_id=UUID(house_id))
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return str(room.id)


def create_device(client, token, room_id, name="Auto Device", device_type=DeviceType.THERMOSTAT.value):
    resp = client.post(
        "/devices/create",
        json={"name": name, "device_type": device_type, "room_id": room_id},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    devices = client.get("/devices/get", headers=auth_header(token)).json()
    return next(d["id"] for d in devices if d["name"] == name)


def setup_device(client, db_session, user_data=None, device_name="Auto Device", device_type=DeviceType.THERMOSTAT.value):
    """Create user, house, room, device. Returns (token, device_id)."""
    _, token = create_user_and_login(client, user_data)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id)
    device_id = create_device(client, token, room_id, name=device_name, device_type=device_type)
    return token, device_id


def create_automation(client, token, device_id, **overrides):
    payload = {
        "name": "Temp Alert",
        "trigger_type": AutomationTriggerType.TEMPERATURE.value,
        "trigger_value": "24",
        "execution_day": None,
        "turn_on": True,
        "device_id": device_id,
    }
    payload.update(overrides)
    return client.post("/automations/create", json=payload, headers=auth_header(token))


def get_automations(client, token):
    resp = client.get("/automations/get", headers=auth_header(token))
    assert resp.status_code == 200
    return resp.json()["automations"]


def first_automation_id(client, token):
    automations = get_automations(client, token)
    return automations[0]["id"]


# ── POST /automations/create ─────────────────────────────────────────────────

class TestCreateAutomation:

    def test_create_temperature_automation_success(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        resp = create_automation(client, token, device_id, name="High Temp")
        assert resp.status_code == 200

        automations = get_automations(client, token)
        assert len(automations) == 1
        created = automations[0]
        assert created["name"] == "High Temp"
        assert created["trigger_type"] == AutomationTriggerType.TEMPERATURE.value
        assert created["trigger_value"] == "24"
        assert created["turn_on"] is True
        assert created["device_id"] == device_id

    def test_create_time_automation_normalizes_dotted_value(self, client, db_session):
        """A dotted time like '12.30' should be normalized to '12:30'."""
        token, device_id = setup_device(client, db_session)
        resp = create_automation(
            client, token, device_id,
            name="Dotted Time",
            trigger_type=AutomationTriggerType.TIME.value,
            trigger_value="12.30",
            execution_day=2,
        )
        assert resp.status_code == 200
        assert get_automations(client, token)[0]["trigger_value"] == "12:30"

    def test_create_time_automation_without_value_rejected(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        resp = create_automation(
            client, token, device_id,
            trigger_type=AutomationTriggerType.TIME.value,
            trigger_value=None,
        )
        assert resp.status_code == 422

    def test_create_time_automation_invalid_format_rejected(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        resp = create_automation(
            client, token, device_id,
            trigger_type=AutomationTriggerType.TIME.value,
            trigger_value="not-a-time",
        )
        assert resp.status_code == 422

    def test_create_automation_execution_day_out_of_range(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        resp = create_automation(client, token, device_id, execution_day=7)
        assert resp.status_code == 422

    def test_create_automation_device_not_found(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = create_automation(client, token, str(uuid4()))
        assert resp.status_code == 404
        assert "device not found" in resp.json()["detail"].lower()

    def test_create_automation_device_belongs_to_another_user(self, client, db_session):
        token1, device_id = setup_device(client, db_session, user_data=TEST_USER)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = create_automation(client, token2, device_id)
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_create_automation_missing_name(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        resp = client.post(
            "/automations/create",
            json={"trigger_type": AutomationTriggerType.TEMPERATURE.value, "trigger_value": "24", "device_id": device_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_automation_missing_device_id(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.post(
            "/automations/create",
            json={"name": "x", "trigger_type": AutomationTriggerType.TEMPERATURE.value, "trigger_value": "24"},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_automation_invalid_trigger_type(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        resp = client.post(
            "/automations/create",
            json={"name": "x", "trigger_type": 9999, "trigger_value": "24", "device_id": device_id},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_create_automation_unauthenticated(self, client, db_session):
        resp = client.post(
            "/automations/create",
            json={"name": "x", "trigger_type": AutomationTriggerType.TEMPERATURE.value, "trigger_value": "24", "device_id": str(uuid4())},
        )
        assert resp.status_code in (401, 403)


# ── GET /automations/get ──────────────────────────────────────────────────────

class TestGetAutomations:

    def test_get_automations_empty(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.get("/automations/get", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["automations"] == []

    def test_get_automations_returns_created(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        create_automation(client, token, device_id, name="A")
        create_automation(client, token, device_id, name="B")

        automations = get_automations(client, token)
        assert len(automations) == 2
        assert {a["name"] for a in automations} == {"A", "B"}

    def test_get_automations_only_own(self, client, db_session):
        token1, device_id_1 = setup_device(client, db_session, user_data=TEST_USER)
        create_automation(client, token1, device_id_1, name="User1 Auto")

        token2, device_id_2 = setup_device(client, db_session, user_data=TEST_USER_2)
        create_automation(client, token2, device_id_2, name="User2 Auto")

        automations_1 = get_automations(client, token1)
        assert len(automations_1) == 1
        assert automations_1[0]["name"] == "User1 Auto"

        automations_2 = get_automations(client, token2)
        assert len(automations_2) == 1
        assert automations_2[0]["name"] == "User2 Auto"

    def test_get_automations_unauthenticated(self, client):
        resp = client.get("/automations/get")
        assert resp.status_code in (401, 403)


# ── GET /automations/get_id/{automation_id} ──────────────────────────────────

class TestGetAutomationById:

    def test_get_automation_by_id_success(self, client, db_session):
        token, device_id = setup_device(client, db_session)
        create_automation(client, token, device_id, name="Lookup")
        automation_id = first_automation_id(client, token)

        resp = client.get(f"/automations/get_id/{automation_id}", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.json()["automation"]
        assert body["id"] == automation_id
        assert body["name"] == "Lookup"
        assert body["device_id"] == device_id

    def test_get_automation_by_id_not_found(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.get(f"/automations/get_id/{uuid4()}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_get_automation_by_id_belongs_to_another_user(self, client, db_session):
        token1, device_id = setup_device(client, db_session, user_data=TEST_USER)
        create_automation(client, token1, device_id)
        automation_id = first_automation_id(client, token1)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.get(f"/automations/get_id/{automation_id}", headers=auth_header(token2))
        assert resp.status_code == 403

    def test_get_automation_by_id_invalid_uuid(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.get("/automations/get_id/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_get_automation_by_id_unauthenticated(self, client):
        resp = client.get(f"/automations/get_id/{uuid4()}")
        assert resp.status_code in (401, 403)


# ── PUT /automations/update ──────────────────────────────────────────────────

class TestUpdateAutomation:

    def _setup_automation(self, client, db_session, user_data=None):
        token, device_id = setup_device(client, db_session, user_data=user_data)
        create_automation(client, token, device_id, name="Original")
        return token, device_id, first_automation_id(client, token)

    def test_update_automation_name(self, client, db_session):
        token, _, automation_id = self._setup_automation(client, db_session)
        resp = client.put(
            "/automations/update",
            json={"automation_id": automation_id, "name": "Renamed"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        body = client.get(f"/automations/get_id/{automation_id}", headers=auth_header(token)).json()["automation"]
        assert body["name"] == "Renamed"

    def test_update_automation_turn_on_and_parameters(self, client, db_session):
        token, _, automation_id = self._setup_automation(client, db_session)
        resp = client.put(
            "/automations/update",
            json={"automation_id": automation_id, "turn_on": False, "parameters": {"power_setting": 60}},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        body = client.get(f"/automations/get_id/{automation_id}", headers=auth_header(token)).json()["automation"]
        assert body["turn_on"] is False
        assert body["parameters"] == {"power_setting": 60}

    def test_update_automation_to_time_trigger_value(self, client, db_session):
        token, _, automation_id = self._setup_automation(client, db_session)
        resp = client.put(
            "/automations/update",
            json={
                "automation_id": automation_id,
                "trigger_type": AutomationTriggerType.TIME.value,
                "trigger_value": "08:15",
                "execution_day": 1,
            },
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        body = client.get(f"/automations/get_id/{automation_id}", headers=auth_header(token)).json()["automation"]
        assert body["trigger_type"] == AutomationTriggerType.TIME.value
        assert body["trigger_value"] == "08:15"
        assert body["execution_day"] == 1

    def test_update_to_time_trigger_with_incompatible_existing_value_rejected(self, client, db_session):
        """Switching a TEMPERATURE automation (value '24') to TIME without a valid
        time value should be rejected by the endpoint's guard (400)."""
        token, _, automation_id = self._setup_automation(client, db_session)
        resp = client.put(
            "/automations/update",
            json={"automation_id": automation_id, "trigger_type": AutomationTriggerType.TIME.value},
            headers=auth_header(token),
        )
        assert resp.status_code == 400
        assert "hh:mm" in resp.json()["detail"].lower()

    def test_update_automation_invalid_time_value_rejected(self, client, db_session):
        token, _, automation_id = self._setup_automation(client, db_session)
        resp = client.put(
            "/automations/update",
            json={
                "automation_id": automation_id,
                "trigger_type": AutomationTriggerType.TIME.value,
                "trigger_value": "99:99",
            },
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_update_automation_execution_day_out_of_range(self, client, db_session):
        token, _, automation_id = self._setup_automation(client, db_session)
        resp = client.put(
            "/automations/update",
            json={"automation_id": automation_id, "execution_day": 9},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_update_automation_not_found(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.put(
            "/automations/update",
            json={"automation_id": str(uuid4()), "name": "Ghost"},
            headers=auth_header(token),
        )
        assert resp.status_code == 404

    def test_update_automation_belongs_to_another_user(self, client, db_session):
        token1, _, automation_id = self._setup_automation(client, db_session, user_data=TEST_USER)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.put(
            "/automations/update",
            json={"automation_id": automation_id, "name": "Hacked"},
            headers=auth_header(token2),
        )
        assert resp.status_code == 403

        # The original automation must be unchanged.
        body = client.get(f"/automations/get_id/{automation_id}", headers=auth_header(token1)).json()["automation"]
        assert body["name"] == "Original"

    def test_update_automation_missing_id(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.put("/automations/update", json={"name": "x"}, headers=auth_header(token))
        assert resp.status_code == 422

    def test_update_automation_unauthenticated(self, client):
        resp = client.put("/automations/update", json={"automation_id": str(uuid4()), "name": "x"})
        assert resp.status_code in (401, 403)


# ── DELETE /automations/delete/{automation_id} ───────────────────────────────

class TestDeleteAutomation:

    def _setup_automation(self, client, db_session, user_data=None):
        token, device_id = setup_device(client, db_session, user_data=user_data)
        create_automation(client, token, device_id, name="Deletable")
        return token, first_automation_id(client, token)

    def test_delete_automation_success(self, client, db_session):
        token, automation_id = self._setup_automation(client, db_session)
        resp = client.delete(f"/automations/delete/{automation_id}", headers=auth_header(token))
        assert resp.status_code == 200
        assert get_automations(client, token) == []

    def test_delete_automation_verify_gone_by_id(self, client, db_session):
        token, automation_id = self._setup_automation(client, db_session)
        client.delete(f"/automations/delete/{automation_id}", headers=auth_header(token))
        resp = client.get(f"/automations/get_id/{automation_id}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_delete_automation_not_found(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.delete(f"/automations/delete/{uuid4()}", headers=auth_header(token))
        assert resp.status_code == 404

    def test_delete_automation_belongs_to_another_user(self, client, db_session):
        token1, automation_id = self._setup_automation(client, db_session, user_data=TEST_USER)

        create_test_user(client, TEST_USER_2)
        token2 = get_auth_token(client, TEST_USER_2["username"], TEST_USER_2["password"])

        resp = client.delete(f"/automations/delete/{automation_id}", headers=auth_header(token2))
        assert resp.status_code == 403
        # Still present for the owner.
        assert len(get_automations(client, token1)) == 1

    def test_delete_automation_twice(self, client, db_session):
        token, automation_id = self._setup_automation(client, db_session)
        first = client.delete(f"/automations/delete/{automation_id}", headers=auth_header(token))
        assert first.status_code == 200
        second = client.delete(f"/automations/delete/{automation_id}", headers=auth_header(token))
        assert second.status_code == 404

    def test_delete_automation_invalid_uuid(self, client, db_session):
        _, token = create_user_and_login(client)
        resp = client.delete("/automations/delete/not-a-uuid", headers=auth_header(token))
        assert resp.status_code == 422

    def test_delete_automation_unauthenticated(self, client):
        resp = client.delete(f"/automations/delete/{uuid4()}")
        assert resp.status_code in (401, 403)
