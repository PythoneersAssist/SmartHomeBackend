import asyncio
import logging
from os import getenv

from sqlalchemy.orm import Session

from api.energy.endpoints import (
    _collect_household_energy,
    _collect_room_energy,
    _collect_device_energy,
    _current_hour_slot_iso,
    _upsert_household_energy_snapshot,
    _upsert_room_energy_snapshot,
    _upsert_device_energy_snapshot,
)
from database.database import SessionLocal
from database.models import House, Room, Device


logger = logging.getLogger(__name__)


def _positive_float_from_env(name: str, default: float) -> float:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _history_interval_seconds() -> float:
    return _positive_float_from_env("ENERGY_HISTORY_SCHEDULER_INTERVAL_SECONDS", 3600.0)


def is_energy_history_scheduler_enabled() -> bool:
    return getenv("ENERGY_HISTORY_SCHEDULER_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}


def run_energy_history_snapshot_cycle(db: Session) -> int:
    houses = db.query(House).all()
    if not houses:
        return 0

    snapshot_slot = _current_hour_slot_iso()
    captured = 0

    for house in houses:
        try:
            device_data, total_watts, active_count = _collect_household_energy(db, house.id)
            _upsert_household_energy_snapshot(
                db=db,
                house_id=house.id,
                total_watts=total_watts,
                active_devices=active_count,
                total_devices=len(device_data),
                hour_slot=snapshot_slot,
            )
            captured += 1
        except Exception:
            db.rollback()
            logger.exception("Failed to capture hourly energy snapshot for house_id=%s", house.id)

    rooms = db.query(Room).all()
    for room in rooms:
        try:
            device_data, total_watts, active_count = _collect_room_energy(db, room.id)
            _upsert_room_energy_snapshot(
                db=db,
                room_id=room.id,
                total_watts=total_watts,
                active_devices=active_count,
                total_devices=len(device_data),
                hour_slot=snapshot_slot,
            )
        except Exception:
            db.rollback()
            logger.exception("Failed to capture hourly energy snapshot for room_id=%s", room.id)

    devices = db.query(Device).all()
    for device in devices:
        try:
            data = _collect_device_energy(db, device.id)
            if data is not None:
                _upsert_device_energy_snapshot(
                    db=db,
                    device_id=device.id,
                    estimated_watts=data["estimated_watts"],
                    is_on=data["is_on"],
                    hour_slot=snapshot_slot,
                )
        except Exception:
            db.rollback()
            logger.exception("Failed to capture hourly energy snapshot for device_id=%s", device.id)

    return captured


class EnergyHistoryScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="energy-history-scheduler")

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
                captured = run_energy_history_snapshot_cycle(db)
                if captured:
                    logger.info("Captured hourly energy snapshots for %s houses", captured)
            except asyncio.CancelledError:
                db.close()
                raise
            except Exception:
                logger.exception("Energy history scheduler iteration failed")
            finally:
                db.close()

            await asyncio.sleep(_history_interval_seconds())


energy_history_scheduler = EnergyHistoryScheduler()
