from datetime import datetime, timedelta, timezone

from database.enums import AutomationTriggerType, DeviceType, FloorType
from database.models import AutomationExecution, AutomationSchedulerState, Room
from api.automations.scheduler import run_time_automation_scheduler_cycle, run_time_scheduler_iteration, to_utc_iso
from tests.conftest import auth_header, create_user_and_login


UTC = timezone.utc


def create_house(client, token, data=None):
    payload = data or {"name": "Scheduler House", "description": "Scheduler testing"}
    response = client.post("/home/create", json=payload, headers=auth_header(token))
    assert response.status_code == 200

    houses = client.get("/home/get", headers=auth_header(token)).json()["houses"]
    for house in houses:
        if house["name"] == payload["name"]:
            return house["id"]

    raise AssertionError("House was not created")


def create_room_in_db(db_session, house_id, name="Scheduler Room", floor=FloorType.FLOOR_1):
    from uuid import UUID

    room = Room(name=name, floor=floor, house_id=UUID(house_id))
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return str(room.id)


def create_device(client, token, room_id, name="Scheduler Device", device_type=DeviceType.THERMOSTAT.value):
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


def create_time_automation(client, token, device_id, name, trigger_value, execution_day, turn_on=True, parameters=None):
    payload = {
        "name": name,
        "trigger_type": AutomationTriggerType.TIME.value,
        "trigger_value": trigger_value,
        "execution_day": execution_day,
        "turn_on": turn_on,
        "device_id": device_id,
    }
    if parameters is not None:
        payload["parameters"] = parameters

    response = client.post(
        "/automations/create",
        json=payload,
        headers=auth_header(token),
    )
    assert response.status_code == 200


def get_device_parameters(client, token, device_id):
    response = client.get(f"/devices/get_id/{device_id}", headers=auth_header(token))
    assert response.status_code == 200
    return response.json()["parameters"]


def test_time_scheduler_executes_due_automation(client, db_session):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id)
    device_id = create_device(client, token, room_id)

    due_time = datetime(2026, 4, 13, 12, 30, 0, tzinfo=UTC)
    create_time_automation(
        client,
        token,
        device_id,
        name="Turn On At Noon",
        trigger_value=due_time.strftime("%H:%M:%S"),
        execution_day=due_time.weekday(),
    )

    executed = run_time_automation_scheduler_cycle(
        due_time - timedelta(minutes=1),
        due_time + timedelta(minutes=1),
        db=db_session,
    )

    assert executed == 1
    parameters = get_device_parameters(client, token, device_id)
    assert parameters["status"] is True

    logs = db_session.query(AutomationExecution).all()
    assert len(logs) == 1
    assert logs[0].scheduled_for == to_utc_iso(due_time)
    assert logs[0].status == "executed"


def test_time_scheduler_can_turn_device_off(client, db_session):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id)
    device_id = create_device(client, token, room_id, name="Off Automation Device")

    status_update = client.put(
        "/devices/update",
        json={"device_id": device_id, "parameters": {"status": True}},
        headers=auth_header(token),
    )
    assert status_update.status_code == 200

    due_time = datetime(2026, 4, 13, 12, 45, 0, tzinfo=UTC)
    create_time_automation(
        client,
        token,
        device_id,
        name="Turn Off At Noon",
        trigger_value=due_time.strftime("%H:%M:%S"),
        execution_day=due_time.weekday(),
        turn_on=False,
    )

    executed = run_time_automation_scheduler_cycle(
        due_time - timedelta(minutes=1),
        due_time + timedelta(minutes=1),
        db=db_session,
    )

    assert executed == 1
    parameters = get_device_parameters(client, token, device_id)
    assert parameters["status"] is False


def test_time_scheduler_can_update_device_parameters(client, db_session):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id)
    device_id = create_device(
        client,
        token,
        room_id,
        name="Oven Automation Device",
        device_type=DeviceType.OVEN.value,
    )

    due_time = datetime(2026, 4, 16, 7, 15, 0, tzinfo=UTC)
    create_time_automation(
        client,
        token,
        device_id,
        name="Set Oven Power",
        trigger_value=due_time.strftime("%H:%M:%S"),
        execution_day=due_time.weekday(),
        turn_on=True,
        parameters={"power_setting": 75},
    )

    executed = run_time_automation_scheduler_cycle(
        due_time - timedelta(minutes=1),
        due_time + timedelta(minutes=1),
        db=db_session,
    )

    assert executed == 1
    parameters = get_device_parameters(client, token, device_id)
    assert parameters["status"] is True
    assert parameters["power_setting"] == 75


def test_time_scheduler_cycle_is_idempotent(client, db_session):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id)
    device_id = create_device(client, token, room_id, name="Idempotent Device")

    due_time = datetime(2026, 4, 14, 8, 0, 0, tzinfo=UTC)
    create_time_automation(
        client,
        token,
        device_id,
        name="Run Once",
        trigger_value=due_time.strftime("%H:%M"),
        execution_day=due_time.weekday(),
    )

    first = run_time_automation_scheduler_cycle(
        due_time - timedelta(minutes=1),
        due_time + timedelta(minutes=1),
        db=db_session,
    )
    second = run_time_automation_scheduler_cycle(
        due_time - timedelta(minutes=1),
        due_time + timedelta(minutes=1),
        db=db_session,
    )

    assert first == 1
    assert second == 0

    logs = db_session.query(AutomationExecution).all()
    assert len(logs) == 1


def test_time_scheduler_recovers_after_restart_window(client, db_session):
    _, token = create_user_and_login(client)
    house_id = create_house(client, token)
    room_id = create_room_in_db(db_session, house_id)
    device_id = create_device(client, token, room_id, name="Recovery Device")

    due_time = datetime(2026, 4, 15, 6, 45, 0, tzinfo=UTC)
    create_time_automation(
        client,
        token,
        device_id,
        name="Recovery Run",
        trigger_value=due_time.strftime("%H:%M:%S"),
        execution_day=due_time.weekday(),
    )

    db_session.add(
        AutomationSchedulerState(
            id=1,
            last_checked_at=to_utc_iso(due_time - timedelta(minutes=5)),
        )
    )
    db_session.commit()

    executed = run_time_scheduler_iteration(db_session, now=due_time + timedelta(minutes=5))
    assert executed == 1

    state = db_session.query(AutomationSchedulerState).filter(AutomationSchedulerState.id == 1).first()
    assert state is not None
    assert state.last_checked_at == to_utc_iso(due_time + timedelta(minutes=5))

    executed_after_restart = run_time_scheduler_iteration(db_session, now=due_time + timedelta(minutes=10))
    assert executed_after_restart == 0
