"""Tests for features added from TODO.md: device presets, password reset,
account deletion, and household temperature simulation."""

from uuid import UUID

from database.enums import DeviceType, FloorType
from database.models import Room, Device
from api.auth.endpoints import PASSWORD_RESET_PURPOSE
from api.users.endpoints import ACCOUNT_DELETION_PURPOSE
from api.simulation.scheduler import run_temperature_simulation_cycle
from utils.security import create_purposed_token
from tests.conftest import (
    TEST_USER,
    create_test_user,
    get_auth_token,
    auth_header,
    create_user_and_login,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_house(client, token, name="Preset House"):
    client.post("/home/create", json={"name": name, "description": "x"}, headers=auth_header(token))
    houses = client.get("/home/get", headers=auth_header(token)).json()["houses"]
    return next(h["id"] for h in houses if h["name"] == name)


def _create_room(db_session, house_id, name="Room"):
    room = Room(name=name, floor=FloorType.FLOOR_1, house_id=UUID(house_id))
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return str(room.id)


def _create_device(client, token, name, device_type, room_id):
    client.post(
        "/devices/create",
        json={"name": name, "device_type": device_type, "room_id": room_id},
        headers=auth_header(token),
    )
    devices = client.get("/devices/get", headers=auth_header(token)).json()
    return next(d["id"] for d in devices if d["name"] == name)


def _get_user_id(client, token):
    return client.get("/user/get", headers=auth_header(token)).json()["id"]


# ── Device presets ──────────────────────────────────────────────────────────

class TestPresets:

    def test_list_presets(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/presets/get", headers=auth_header(token))
        assert resp.status_code == 200
        presets = resp.json()["presets"]
        assert any(p["id"] == "samsung-tv-movie" for p in presets)

    def test_list_presets_filtered_by_type(self, client):
        _, token = create_user_and_login(client)
        resp = client.get(f"/presets/get?device_type={DeviceType.TV.value}", headers=auth_header(token))
        assert resp.status_code == 200
        presets = resp.json()["presets"]
        assert presets
        assert all(p["device_type"] == DeviceType.TV.value for p in presets)

    def test_get_preset_by_id(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/presets/get/samsung-tv-movie", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["preset"]["brand"] == "Samsung"

    def test_get_preset_not_found(self, client):
        _, token = create_user_and_login(client)
        resp = client.get("/presets/get/nope", headers=auth_header(token))
        assert resp.status_code == 404

    def test_apply_preset_success(self, client, db_session):
        _, token = create_user_and_login(client)
        house_id = _create_house(client, token)
        room_id = _create_room(db_session, house_id)
        device_id = _create_device(client, token, "Living TV", DeviceType.TV.value, room_id)

        resp = client.post(
            "/presets/apply",
            json={"device_id": device_id, "preset_id": "samsung-tv-movie"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200

        params = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token)).json()["parameters"]
        assert params["status"] is True
        assert params["volume"] == 25
        assert params["picture_mode"] == "movie"

    def test_apply_preset_wrong_device_type(self, client, db_session):
        _, token = create_user_and_login(client)
        house_id = _create_house(client, token)
        room_id = _create_room(db_session, house_id)
        device_id = _create_device(client, token, "Kitchen Light", DeviceType.LIGHT.value, room_id)

        resp = client.post(
            "/presets/apply",
            json={"device_id": device_id, "preset_id": "samsung-tv-movie"},
            headers=auth_header(token),
        )
        assert resp.status_code == 400

    def test_apply_preset_requires_auth(self, client):
        resp = client.post("/presets/apply", json={"device_id": "x", "preset_id": "samsung-tv-movie"})
        assert resp.status_code in (401, 403, 422)


# ── Password reset ────────────────────────────────────────────────────────────

class TestPasswordReset:

    def test_forgot_password_unknown_email_returns_generic(self, client):
        create_user_and_login(client)
        resp = client.post("/forgot-password", json={"email": "nobody@example.com"})
        assert resp.status_code == 200
        assert "reset link" in resp.json()["message"].lower()

    def test_forgot_password_known_email_returns_generic(self, client):
        create_user_and_login(client)
        resp = client.post("/forgot-password", json={"email": TEST_USER["email"]})
        assert resp.status_code == 200

    def test_reset_password_success(self, client):
        _, token = create_user_and_login(client)
        user_id = _get_user_id(client, token)
        reset_token = create_purposed_token(user_id, PASSWORD_RESET_PURPOSE, 30)

        new_password = "BrandNewPass9!"
        resp = client.post("/reset-password", json={"token": reset_token, "new_password": new_password})
        assert resp.status_code == 200

        # Old password should no longer work; new one should.
        old = client.post("/token", data={"username": TEST_USER["username"], "password": TEST_USER["password"]})
        assert old.status_code == 401
        new = client.post("/token", data={"username": TEST_USER["username"], "password": new_password})
        assert new.status_code == 200

    def test_reset_password_invalid_token(self, client):
        resp = client.post("/reset-password", json={"token": "garbage", "new_password": "BrandNewPass9!"})
        assert resp.status_code == 400

    def test_reset_password_weak_password_rejected(self, client):
        _, token = create_user_and_login(client)
        user_id = _get_user_id(client, token)
        reset_token = create_purposed_token(user_id, PASSWORD_RESET_PURPOSE, 30)
        resp = client.post("/reset-password", json={"token": reset_token, "new_password": "weak"})
        assert resp.status_code == 400

    def test_reset_password_rejects_wrong_purpose_token(self, client):
        _, token = create_user_and_login(client)
        user_id = _get_user_id(client, token)
        # A deletion token must not be usable to reset a password.
        wrong = create_purposed_token(user_id, ACCOUNT_DELETION_PURPOSE, 30)
        resp = client.post("/reset-password", json={"token": wrong, "new_password": "BrandNewPass9!"})
        assert resp.status_code == 400


# ── Account deletion ──────────────────────────────────────────────────────────

class TestAccountDeletion:

    def test_request_deletion_requires_auth(self, client):
        resp = client.post("/user/request-deletion")
        assert resp.status_code in (401, 403)

    def test_request_deletion_success(self, client):
        _, token = create_user_and_login(client)
        resp = client.post("/user/request-deletion", headers=auth_header(token))
        assert resp.status_code == 200

    def test_confirm_deletion_removes_account(self, client):
        _, token = create_user_and_login(client)
        user_id = _get_user_id(client, token)
        deletion_token = create_purposed_token(user_id, ACCOUNT_DELETION_PURPOSE, 30)

        resp = client.post("/user/confirm-deletion", json={"token": deletion_token})
        assert resp.status_code == 200

        # The user can no longer authenticate.
        login = client.post("/token", data={"username": TEST_USER["username"], "password": TEST_USER["password"]})
        assert login.status_code == 401

    def test_confirm_deletion_invalid_token(self, client):
        resp = client.post("/user/confirm-deletion", json={"token": "garbage"})
        assert resp.status_code == 400

    def test_confirm_deletion_rejects_wrong_purpose_token(self, client):
        _, token = create_user_and_login(client)
        user_id = _get_user_id(client, token)
        wrong = create_purposed_token(user_id, PASSWORD_RESET_PURPOSE, 30)
        resp = client.post("/user/confirm-deletion", json={"token": wrong})
        assert resp.status_code == 400


# ── Temperature simulation ────────────────────────────────────────────────────

class TestTemperatureSimulation:

    def _seed_room(self, client, db_session):
        _, token = create_user_and_login(client)
        house_id = _create_house(client, token, name="Sim House")
        room_id = _create_room(db_session, house_id, name="Sim Room")
        return token, room_id

    def test_thermostat_drifts_toward_active_heater_target(self, client, db_session):
        token, room_id = self._seed_room(client, db_session)
        thermostat_id = _create_device(client, token, "Thermo", DeviceType.THERMOSTAT.value, room_id)
        heater_id = _create_device(client, token, "Heater", DeviceType.HEATER.value, room_id)

        # Thermostat starts at 21; turn on a heater targeting 25.
        client.put("/devices/update", json={"device_id": heater_id, "parameters": {"status": True, "target_temperature": 25.0, "power": 100}}, headers=auth_header(token))

        before = client.get(f"/devices/get_id/{thermostat_id}", headers=auth_header(token)).json()["parameters"]["temperature"]
        updated = run_temperature_simulation_cycle(db_session)
        assert updated >= 1
        after = client.get(f"/devices/get_id/{thermostat_id}", headers=auth_header(token)).json()["parameters"]["temperature"]
        # Temperature should move upward toward the heater target.
        assert after > before
        assert after <= 25.0

    def test_thermostat_drifts_toward_baseline_when_idle(self, client, db_session):
        token, room_id = self._seed_room(client, db_session)
        thermostat_id = _create_device(client, token, "Thermo", DeviceType.THERMOSTAT.value, room_id)
        # Push thermostat well above baseline (default 20.0), no active conditioning.
        client.put("/devices/update", json={"device_id": thermostat_id, "parameters": {"status": True, "temperature": 30.0}}, headers=auth_header(token))

        run_temperature_simulation_cycle(db_session)
        after = client.get(f"/devices/get_id/{thermostat_id}", headers=auth_header(token)).json()["parameters"]["temperature"]
        # Should drift back down toward the 20.0 baseline.
        assert after < 30.0

    def test_simulation_pushes_live_websocket_event(self, client, db_session):
        token, room_id = self._seed_room(client, db_session)
        thermostat_id = _create_device(client, token, "Thermo", DeviceType.THERMOSTAT.value, room_id)
        heater_id = _create_device(client, token, "Heater", DeviceType.HEATER.value, room_id)
        client.put("/devices/update", json={"device_id": heater_id, "parameters": {"status": True, "target_temperature": 25.0, "power": 100}}, headers=auth_header(token))

        with client.websocket_connect(f"/notifications/ws?token={token}") as websocket:
            # Drain the initial "connected" event.
            for _ in range(10):
                if websocket.receive_json().get("event") == "connected":
                    break

            run_temperature_simulation_cycle(db_session)

            event = None
            for _ in range(10):
                message = websocket.receive_json()
                if message.get("event") == "deviceParametersChanged":
                    event = message
                    break

        assert event is not None
        assert event["deviceId"] == thermostat_id
        assert "temperature" in event["parameters"]
        # Transient event: must not be added to the persisted notification bell.
        assert "notificationId" not in event
