
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from database.database import get_db
from database.models import User, House, Room, Device, EnergyHistory, RoomEnergyHistory, DeviceEnergyHistory
from api.auth.endpoints import get_current_user

router = APIRouter(prefix="/energy")
logger = logging.getLogger(__name__)
UTC = timezone.utc

# Estimated wattage per device type (value from DeviceType enum)
DEVICE_WATTAGE = {
    0: 10,     # LIGHT
    1: 15,     # LED_STRIP
    2: 5,      # OUTLET
    3: 50,     # FANS
    4: 5,      # THERMOSTAT
    5: 1500,   # AIR_CONDITIONER
    6: 30,     # HUMIDIFIER
    7: 1200,   # HEATER
    8: 100,    # GARAGE_DOOR
    9: 100,    # GATE
    10: 120,   # TV
    11: 30,    # SPEAKER
    12: 2000,  # OVEN
    13: 1800,  # DISHWASHER
    14: 500,   # WASHER
    15: 3000,  # DRYER
    16: 150,   # REFRIGERATOR
    17: 10,    # CURTAINS
    18: 10,    # ROUTER
    19: 10,    # HUB
    20: 50,    # OTHER
    -1: 0,     # UNKNOWN
}


def _hour_slot_from_datetime(timestamp: datetime) -> str:
    normalized = timestamp.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _current_hour_slot_iso() -> str:
    return _hour_slot_from_datetime(datetime.now(UTC))


def _hour_slot_to_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _get_energy_cost_rate() -> float:
    from os import getenv
    raw = getenv("ENERGY_COST_PER_KWH", "0.22")
    try:
        rate = float(raw)
        return max(rate, 0.0)
    except (TypeError, ValueError):
        return 0.22


def _watts_to_kwh(watts: float, hours: int) -> float:
    return (watts / 1000.0) * hours


def _compute_device_energy(device: Device) -> dict:
    params = device.parameters or {}
    is_on = params.get("status", False)
    device_type_val = device.type.value if device.type is not None else -1
    wattage = DEVICE_WATTAGE.get(device_type_val, 0)
    current_watts = wattage if is_on else 0

    return {
        "device_id": str(device.id),
        "device_name": device.name,
        "device_type": device_type_val,
        "is_on": is_on,
        "estimated_watts": current_watts,
    }


def _collect_household_energy(db: Session, house_id: UUID) -> tuple[list[dict], int, int]:
    devices = (
        db.query(Device)
        .join(Room, Device.room_id == Room.id)
        .filter(Room.house_id == house_id)
        .all()
    )

    device_data = [_compute_device_energy(device) for device in devices]
    total_watts = sum(item["estimated_watts"] for item in device_data)
    active_count = sum(1 for item in device_data if item["is_on"])

    return device_data, total_watts, active_count


def _upsert_household_energy_snapshot(
    db: Session,
    house_id: UUID,
    total_watts: int,
    active_devices: int,
    total_devices: int,
    hour_slot: str | None = None,
) -> None:
    snapshot_slot = hour_slot or _current_hour_slot_iso()
    existing = (
        db.query(EnergyHistory)
        .filter(EnergyHistory.house_id == house_id, EnergyHistory.hour_slot == snapshot_slot)
        .first()
    )

    if existing is None:
        db.add(EnergyHistory(
            house_id=house_id,
            hour_slot=snapshot_slot,
            total_estimated_watts=total_watts,
            active_devices=active_devices,
            total_devices=total_devices,
        ))
    else:
        existing.total_estimated_watts = total_watts
        existing.active_devices = active_devices
        existing.total_devices = total_devices

    try:
        db.commit()
    except IntegrityError:
        # If a concurrent writer inserted the same house/hour row, update that row instead.
        db.rollback()
        row = (
            db.query(EnergyHistory)
            .filter(EnergyHistory.house_id == house_id, EnergyHistory.hour_slot == snapshot_slot)
            .first()
        )
        if row is None:
            raise
        row.total_estimated_watts = total_watts
        row.active_devices = active_devices
        row.total_devices = total_devices
        db.commit()


def _upsert_room_energy_snapshot(
    db: Session,
    room_id: UUID,
    total_watts: int,
    active_devices: int,
    total_devices: int,
    hour_slot: str | None = None,
) -> None:
    snapshot_slot = hour_slot or _current_hour_slot_iso()
    existing = (
        db.query(RoomEnergyHistory)
        .filter(RoomEnergyHistory.room_id == room_id, RoomEnergyHistory.hour_slot == snapshot_slot)
        .first()
    )

    if existing is None:
        db.add(RoomEnergyHistory(
            room_id=room_id,
            hour_slot=snapshot_slot,
            total_estimated_watts=total_watts,
            active_devices=active_devices,
            total_devices=total_devices,
        ))
    else:
        existing.total_estimated_watts = total_watts
        existing.active_devices = active_devices
        existing.total_devices = total_devices

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = (
            db.query(RoomEnergyHistory)
            .filter(RoomEnergyHistory.room_id == room_id, RoomEnergyHistory.hour_slot == snapshot_slot)
            .first()
        )
        if row is None:
            raise
        row.total_estimated_watts = total_watts
        row.active_devices = active_devices
        row.total_devices = total_devices
        db.commit()


def _upsert_device_energy_snapshot(
    db: Session,
    device_id: UUID,
    estimated_watts: int,
    is_on: bool,
    hour_slot: str | None = None,
) -> None:
    snapshot_slot = hour_slot or _current_hour_slot_iso()
    existing = (
        db.query(DeviceEnergyHistory)
        .filter(DeviceEnergyHistory.device_id == device_id, DeviceEnergyHistory.hour_slot == snapshot_slot)
        .first()
    )

    if existing is None:
        db.add(DeviceEnergyHistory(
            device_id=device_id,
            hour_slot=snapshot_slot,
            estimated_watts=estimated_watts,
            is_on=is_on,
        ))
    else:
        existing.estimated_watts = estimated_watts
        existing.is_on = is_on

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = (
            db.query(DeviceEnergyHistory)
            .filter(DeviceEnergyHistory.device_id == device_id, DeviceEnergyHistory.hour_slot == snapshot_slot)
            .first()
        )
        if row is None:
            raise
        row.estimated_watts = estimated_watts
        row.is_on = is_on
        db.commit()


def _collect_room_energy(db: Session, room_id: UUID) -> tuple[list[dict], int, int]:
    devices = db.query(Device).filter(Device.room_id == room_id).all()
    device_data = [_compute_device_energy(device) for device in devices]
    total_watts = sum(item["estimated_watts"] for item in device_data)
    active_count = sum(1 for item in device_data if item["is_on"])
    return device_data, total_watts, active_count


def _collect_device_energy(db: Session, device_id: UUID) -> dict | None:
    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        return None
    return _compute_device_energy(device)


@cbv(router)
class EnergyEndpoints:
    db: Session = Depends(get_db)

    @router.get("/household/{house_id}", tags=["energy"])
    def get_energy_usage_from_household(self, house_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        house = self.db.query(House).filter(House.id == house_id).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="House not found"
            )
        if house.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this house"
            )

        device_data, total_watts, active_count = _collect_household_energy(self.db, house_id)

        try:
            _upsert_household_energy_snapshot(
                db=self.db,
                house_id=house.id,
                total_watts=total_watts,
                active_devices=active_count,
                total_devices=len(device_data),
            )
        except Exception:
            self.db.rollback()
            logger.exception("Failed to persist hourly energy snapshot for house_id=%s", house_id)

        return JSONResponse(
            content={
                "house_id": str(house_id),
                "house_name": house.name,
                "total_devices": len(device_data),
                "active_devices": active_count,
                "total_estimated_watts": total_watts,
                "devices": device_data,
            },
            status_code=status.HTTP_200_OK,
        )

    @router.get("/household/{house_id}/history", tags=["energy"])
    def get_household_energy_history(
        self,
        house_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        hours: int = Query(default=24 * 7, ge=1, le=24 * 365),
    ):
        house = self.db.query(House).filter(House.id == house_id).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="House not found"
            )
        if house.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this house"
            )

        # Keep latest hour fresh whenever history is requested.
        device_data, total_watts, active_count = _collect_household_energy(self.db, house_id)
        try:
            _upsert_household_energy_snapshot(
                db=self.db,
                house_id=house.id,
                total_watts=total_watts,
                active_devices=active_count,
                total_devices=len(device_data),
            )
        except Exception:
            self.db.rollback()
            logger.exception("Failed to persist hourly energy snapshot for history request house_id=%s", house_id)

        end_slot = _current_hour_slot_iso()
        end_dt = _hour_slot_to_datetime(end_slot)
        start_dt = end_dt - timedelta(hours=hours - 1)
        start_slot = _hour_slot_from_datetime(start_dt)

        records = (
            self.db.query(EnergyHistory)
            .filter(EnergyHistory.house_id == house.id, EnergyHistory.hour_slot >= start_slot)
            .order_by(EnergyHistory.hour_slot.asc())
            .all()
        )

        by_slot = {record.hour_slot: record for record in records}
        timeline: list[dict] = []
        cursor = start_dt
        while cursor <= end_dt:
            slot = _hour_slot_from_datetime(cursor)
            record = by_slot.get(slot)
            timeline.append({
                "hour_slot": slot,
                "total_estimated_watts": record.total_estimated_watts if record is not None else 0,
                "active_devices": record.active_devices if record is not None else 0,
                "total_devices": record.total_devices if record is not None else 0,
            })
            cursor += timedelta(hours=1)

        rate = _get_energy_cost_rate()
        total_kwh = sum(
            _watts_to_kwh(h["total_estimated_watts"], 1) for h in timeline
        )

        return JSONResponse(
            content={
                "house_id": str(house.id),
                "house_name": house.name,
                "hours": hours,
                "history": timeline,
                "summary": {
                    "total_kwh": round(total_kwh, 3),
                    "estimated_cost": round(total_kwh * rate, 2),
                    "currency": "USD",
                    "rate_per_kwh": rate,
                },
            },
            status_code=status.HTTP_200_OK,
        )

    @router.get("/room/{room_id}/history", tags=["energy"])
    def get_room_energy_history(
        self,
        room_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        hours: int = Query(default=24 * 7, ge=1, le=24 * 365),
    ):
        room = self.db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        house = self.db.query(House).filter(House.id == room.house_id, House.user_id == current_user.id).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room"
            )

        device_data, total_watts, active_count = _collect_room_energy(self.db, room_id)
        try:
            _upsert_room_energy_snapshot(
                db=self.db,
                room_id=room.id,
                total_watts=total_watts,
                active_devices=active_count,
                total_devices=len(device_data),
            )
        except Exception:
            self.db.rollback()
            logger.exception("Failed to persist hourly energy snapshot for room_id=%s", room_id)

        end_slot = _current_hour_slot_iso()
        end_dt = _hour_slot_to_datetime(end_slot)
        start_dt = end_dt - timedelta(hours=hours - 1)
        start_slot = _hour_slot_from_datetime(start_dt)

        records = (
            self.db.query(RoomEnergyHistory)
            .filter(RoomEnergyHistory.room_id == room.id, RoomEnergyHistory.hour_slot >= start_slot)
            .order_by(RoomEnergyHistory.hour_slot.asc())
            .all()
        )

        by_slot = {record.hour_slot: record for record in records}
        timeline: list[dict] = []
        cursor = start_dt
        while cursor <= end_dt:
            slot = _hour_slot_from_datetime(cursor)
            record = by_slot.get(slot)
            timeline.append({
                "hour_slot": slot,
                "total_estimated_watts": record.total_estimated_watts if record is not None else 0,
                "active_devices": record.active_devices if record is not None else 0,
                "total_devices": record.total_devices if record is not None else 0,
            })
            cursor += timedelta(hours=1)

        rate = _get_energy_cost_rate()
        total_kwh = sum(
            _watts_to_kwh(h["total_estimated_watts"], 1) for h in timeline
        )

        return JSONResponse(
            content={
                "room_id": str(room.id),
                "room_name": room.name,
                "hours": hours,
                "history": timeline,
                "summary": {
                    "total_kwh": round(total_kwh, 3),
                    "estimated_cost": round(total_kwh * rate, 2),
                    "currency": "USD",
                    "rate_per_kwh": rate,
                },
            },
            status_code=status.HTTP_200_OK,
        )

    @router.get("/device/{device_id}/history", tags=["energy"])
    def get_device_energy_history(
        self,
        device_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        hours: int = Query(default=24 * 7, ge=1, le=24 * 365),
    ):
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        house = (
            self.db.query(House)
            .join(Room, House.id == Room.house_id)
            .filter(Room.id == device.room_id, House.user_id == current_user.id)
            .first()
        )
        if not house:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this device"
            )

        data = _collect_device_energy(self.db, device_id)
        try:
            _upsert_device_energy_snapshot(
                db=self.db,
                device_id=device.id,
                estimated_watts=data["estimated_watts"],
                is_on=data["is_on"],
            )
        except Exception:
            self.db.rollback()
            logger.exception("Failed to persist hourly energy snapshot for device_id=%s", device_id)

        end_slot = _current_hour_slot_iso()
        end_dt = _hour_slot_to_datetime(end_slot)
        start_dt = end_dt - timedelta(hours=hours - 1)
        start_slot = _hour_slot_from_datetime(start_dt)

        records = (
            self.db.query(DeviceEnergyHistory)
            .filter(DeviceEnergyHistory.device_id == device.id, DeviceEnergyHistory.hour_slot >= start_slot)
            .order_by(DeviceEnergyHistory.hour_slot.asc())
            .all()
        )

        by_slot = {record.hour_slot: record for record in records}
        timeline: list[dict] = []
        cursor = start_dt
        while cursor <= end_dt:
            slot = _hour_slot_from_datetime(cursor)
            record = by_slot.get(slot)
            timeline.append({
                "hour_slot": slot,
                "estimated_watts": record.estimated_watts if record is not None else 0,
                "is_on": record.is_on if record is not None else False,
            })
            cursor += timedelta(hours=1)

        rate = _get_energy_cost_rate()
        total_kwh = sum(
            _watts_to_kwh(h["estimated_watts"], 1) for h in timeline
        )

        return JSONResponse(
            content={
                "device_id": str(device.id),
                "device_name": device.name,
                "device_type": data["device_type"],
                "hours": hours,
                "history": timeline,
                "summary": {
                    "total_kwh": round(total_kwh, 3),
                    "estimated_cost": round(total_kwh * rate, 2),
                    "currency": "USD",
                    "rate_per_kwh": rate,
                },
            },
            status_code=status.HTTP_200_OK,
        )