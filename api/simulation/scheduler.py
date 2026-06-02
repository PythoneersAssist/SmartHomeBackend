"""
Household temperature simulation.

Periodically nudges each room's thermostat reading toward a target temperature.
The target is driven by the active heating/cooling devices in the same room
(heaters and air conditioners pull the room toward their target_temperature);
when nothing is actively conditioning the room the temperature drifts back
toward an ambient baseline.
"""
import asyncio
import logging
from os import getenv

from sqlalchemy.orm import Session

from api.notifications.ws_manager import notify_device_parameters_changed
from database.database import SessionLocal
from database.enums import DeviceType
from database.models import Device, Room


logger = logging.getLogger(__name__)

# Device types that actively push a room toward their target_temperature.
CONDITIONING_DEVICE_TYPES = (DeviceType.HEATER, DeviceType.AIR_CONDITIONER)


def _float_from_env(name: str, default: float) -> float:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def _positive_float_from_env(name: str, default: float) -> float:
    value = _float_from_env(name, default)
    return value if value > 0 else default


def _interval_seconds() -> float:
    return _positive_float_from_env("TEMPERATURE_SIMULATION_INTERVAL_SECONDS", 60.0)


def _ambient_baseline() -> float:
    return _float_from_env("TEMPERATURE_SIMULATION_BASELINE_C", 20.0)


def _drift_step() -> float:
    """Fraction (0-1) of the gap to the target closed on each cycle."""
    step = _float_from_env("TEMPERATURE_SIMULATION_STEP", 0.1)
    if step <= 0:
        return 0.1
    return min(step, 1.0)


def is_temperature_simulation_enabled() -> bool:
    return getenv("TEMPERATURE_SIMULATION_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}


def _room_target_temperature(devices: list[Device], baseline: float) -> float:
    """Compute the temperature the room is being driven toward."""
    targets: list[float] = []
    for device in devices:
        if device.type not in CONDITIONING_DEVICE_TYPES:
            continue
        params = device.parameters or {}
        if not params.get("status", False):
            continue
        target = params.get("target_temperature")
        try:
            targets.append(float(target))
        except (TypeError, ValueError):
            continue

    if not targets:
        return baseline
    return sum(targets) / len(targets)


def run_temperature_simulation_cycle(db: Session) -> int:
    """Advance the simulated temperature of every thermostat by one step.

    Returns the number of thermostats whose temperature changed.
    """
    baseline = _ambient_baseline()
    step = _drift_step()

    rooms = db.query(Room).all()
    # Collect (user_id, device_id, parameters) for thermostats that changed so we
    # can push live updates only after the transaction is safely committed.
    pending_events: list[tuple[str, str, dict]] = []

    for room in rooms:
        devices = db.query(Device).filter(Device.room_id == room.id).all()
        thermostats = [d for d in devices if d.type == DeviceType.THERMOSTAT]
        if not thermostats:
            continue

        target = _room_target_temperature(devices, baseline)

        for thermostat in thermostats:
            params = dict(thermostat.parameters or {})
            try:
                current = float(params.get("temperature", baseline))
            except (TypeError, ValueError):
                current = baseline

            new_temperature = round(current + step * (target - current), 1)
            if new_temperature == round(current, 1):
                continue

            params["temperature"] = new_temperature
            thermostat.parameters = params

            user_id = None
            if room.house is not None:
                user_id = str(room.house.user_id)
            if user_id is not None:
                pending_events.append((user_id, str(thermostat.id), params))

    if pending_events:
        db.commit()
        for user_id, device_id, parameters in pending_events:
            notify_device_parameters_changed(user_id, device_id, parameters)

    return len(pending_events)


class TemperatureSimulationScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="temperature-simulation")

    async def stop(self) -> None:
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while True:
            db = SessionLocal()
            try:
                updated = run_temperature_simulation_cycle(db)
                if updated:
                    logger.info("Simulated temperature update for %s thermostats", updated)
            except asyncio.CancelledError:
                db.close()
                raise
            except Exception:
                logger.exception("Temperature simulation iteration failed")
            finally:
                db.close()

            await asyncio.sleep(_interval_seconds())


temperature_simulation_scheduler = TemperatureSimulationScheduler()
