from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from database.database import get_db
from database.models import User, House, Room, Device
from database.enums import DeviceType
from devices.models import CreateDeviceModel, UpdateDeviceModel
from auth.endpoints import get_current_user
from utils import device_parameters

router = APIRouter(prefix="/devices")

DEVICE_TYPE_PARAMETERS = {
    DeviceType.LIGHT: device_parameters.DEFAULT_DEVICE,
    DeviceType.LED_STRIP: device_parameters.LED_DEVICE,
    DeviceType.OUTLET: device_parameters.DEFAULT_DEVICE,
    DeviceType.FANS: device_parameters.FAN_DEVICE,
    DeviceType.THERMOSTAT: device_parameters.THERMOSTAT_DEVICE,
    DeviceType.AIR_CONDITIONER: device_parameters.AIR_CONDITIONER_DEVICE,
    DeviceType.HUMIDIFIER: device_parameters.DEFAULT_DEVICE,
    DeviceType.HEATER: device_parameters.HEATER_DEVICE,
    DeviceType.GARAGE_DOOR: device_parameters.DEFAULT_DEVICE,
    DeviceType.GATE: device_parameters.DEFAULT_DEVICE,
    DeviceType.TV: device_parameters.TV_DEVICE,
    DeviceType.SPEAKER: device_parameters.SPEAKER_DEVICE,
    DeviceType.OVEN: device_parameters.OVEN_DEVICE,
    DeviceType.DISHWASHER: device_parameters.DEFAULT_DEVICE,
    DeviceType.WASHER: device_parameters.WASHER_AND_DRIER_DEVICE,
    DeviceType.DRYER: device_parameters.WASHER_AND_DRIER_DEVICE,
    DeviceType.REFRIGERATOR: device_parameters.REFRIGERATOR_DEVICE,
    DeviceType.CURTAINS: device_parameters.DEFAULT_DEVICE,
    DeviceType.ROUTER: device_parameters.DEFAULT_DEVICE,
    DeviceType.HUB: device_parameters.DEFAULT_DEVICE,
    DeviceType.OTHER: device_parameters.DEFAULT_DEVICE,
    DeviceType.UNKNOWN: device_parameters.DEFAULT_DEVICE,
}

def get_default_parameters(device_type: DeviceType) -> dict:
    return DEVICE_TYPE_PARAMETERS.get(device_type, device_parameters.DEFAULT_DEVICE).copy()

@cbv(router)
class DeviceEndpoints:
    db: Session = Depends(get_db)

    def _verify_device_ownership(self, device: Device, user: User) -> House:
        house = (
            self.db.query(House)
            .join(Room, House.id == Room.house_id)
            .filter(Room.id == device.room_id, House.user_id == user.id)
            .first()
        )
        if not house:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this device"
            )
        return house

    @router.post("/create", tags=["device"])
    def create_device(self, data: CreateDeviceModel, current_user: Annotated[User, Depends(get_current_user)]):
        room = self.db.query(Room).filter(Room.id == data.room_id).first()
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

        if self.db.query(Device).filter(Device.room_id == data.room_id, Device.name == data.name).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A device with name '{data.name}' already exists in this room"
            )

        parameters = get_default_parameters(data.device_type)

        self.db.add(Device(
            name=data.name,
            type=data.device_type,
            parameters=parameters,
            room=room
        ))
        self.db.commit()

    @router.get("/get", tags=["device"])
    def get_registered_devices(self, current_user: Annotated[User, Depends(get_current_user)]):
        devices = (
            self.db.query(Device)
            .join(Room, Device.room_id == Room.id)
            .join(House, Room.house_id == House.id)
            .filter(House.user_id == current_user.id)
            .all()
        )

        data = []
        for device in devices:
            data.append({
                "id": str(device.id),
                "name": device.name,
                "type": device.type.value if device.type is not None else None,
                "parameters": device.parameters,
                "room_id": str(device.room_id)
            })

        return JSONResponse(data, status_code=status.HTTP_200_OK)

    @router.get("/get_id/{device_id}", tags=["device"])
    def get_registered_device_by_id(self, device_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return JSONResponse(content=[], status_code=status.HTTP_404_NOT_FOUND)

        self._verify_device_ownership(device, current_user)

        data = {
            "id": str(device.id),
            "name": device.name,
            "type": device.type.value if device.type is not None else None,
            "parameters": device.parameters,
            "room_id": str(device.room_id)
        }

        return JSONResponse(data, status_code=status.HTTP_200_OK)

    @router.put("/update", tags=["device"])
    def update_registered_device_by_id(self, data: UpdateDeviceModel, current_user: Annotated[User, Depends(get_current_user)]):
        device = self.db.query(Device).filter(Device.id == data.device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        self._verify_device_ownership(device, current_user)

        if data.name:
            existing = self.db.query(Device).filter(
                Device.room_id == device.room_id,
                Device.name == data.name,
                Device.id != device.id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A device with that name already exists in this room"
                )
            device.name = data.name

        if data.parameters is not None:
            device.parameters = data.parameters

        self.db.commit()

    @router.delete("/delete/{device_id}", tags=["device"])
    def delete_device_by_id(self, device_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        device = self.db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        self._verify_device_ownership(device, current_user)

        self.db.delete(device)
        self.db.commit()

