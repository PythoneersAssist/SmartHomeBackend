
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from database.database import get_db
from database.models import User, House, Room, Device
from api.auth.endpoints import get_current_user

router = APIRouter(prefix="/energy")

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

        devices = (
            self.db.query(Device)
            .join(Room, Device.room_id == Room.id)
            .filter(Room.house_id == house_id)
            .all()
        )

        device_data = [_compute_device_energy(d) for d in devices]
        total_watts = sum(d["estimated_watts"] for d in device_data)
        active_count = sum(1 for d in device_data if d["is_on"])

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

    @router.get("/room/{room_id}", tags=["energy"])
    def get_energy_usage_from_room(self, room_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
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

        devices = self.db.query(Device).filter(Device.room_id == room_id).all()

        device_data = [_compute_device_energy(d) for d in devices]
        total_watts = sum(d["estimated_watts"] for d in device_data)
        active_count = sum(1 for d in device_data if d["is_on"])

        return JSONResponse(
            content={
                "room_id": str(room_id),
                "room_name": room.name,
                "total_devices": len(device_data),
                "active_devices": active_count,
                "total_estimated_watts": total_watts,
                "devices": device_data,
            },
            status_code=status.HTTP_200_OK,
        )

    @router.get("/device/{device_id}", tags=["energy"])
    def get_energy_usage_from_device(self, device_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
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

        data = _compute_device_energy(device)

        return JSONResponse(
            content=data,
            status_code=status.HTTP_200_OK,
        )