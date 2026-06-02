from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from uuid import UUID

from database.database import get_db
from database.models import User, House, Room, Device
from database.enums import DeviceType
from api.auth.endpoints import get_current_user
from api.presets.models import ApplyPresetModel
from api.notifications.ws_manager import notify_device_status_changed
from utils import device_presets

router = APIRouter(prefix="/presets")


@cbv(router)
class PresetEndpoints:
    db: Session = Depends(get_db)

    @router.get("/get", tags=["preset"])
    def get_presets(
        self,
        current_user: Annotated[User, Depends(get_current_user)],
        device_type: Optional[int] = Query(default=None, description="Optional DeviceType code to filter presets"),
    ):
        type_filter: Optional[DeviceType] = None
        if device_type is not None:
            try:
                type_filter = DeviceType(device_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid device type code '{device_type}'"
                )

        presets = [device_presets.serialize_preset(p) for p in device_presets.list_presets(type_filter)]
        return JSONResponse(
            content={"message": f"Retrieved {len(presets)} presets", "presets": presets},
            status_code=status.HTTP_200_OK
        )

    @router.get("/get/{preset_id}", tags=["preset"])
    def get_preset_by_id(self, preset_id: str, current_user: Annotated[User, Depends(get_current_user)]):
        preset = device_presets.get_preset(preset_id)
        if not preset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preset not found"
            )
        return JSONResponse(
            content={"preset": device_presets.serialize_preset(preset)},
            status_code=status.HTTP_200_OK
        )

    @router.post("/apply", tags=["preset"])
    def apply_preset(self, data: ApplyPresetModel, current_user: Annotated[User, Depends(get_current_user)]):
        preset = device_presets.get_preset(data.preset_id)
        if not preset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preset not found"
            )

        device = self.db.query(Device).filter(Device.id == data.device_id).first()
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

        if device.type != preset["device_type"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This preset cannot be applied to this device type"
            )

        previous_parameters = dict(device.parameters or {})
        # Merge preset values over the current parameters so unrelated keys stay.
        updated_parameters = {**previous_parameters, **preset["parameters"]}
        device.parameters = updated_parameters
        self.db.commit()

        old_status = bool(previous_parameters.get("status", False))
        new_status = bool(updated_parameters.get("status", False))
        if old_status != new_status:
            notify_device_status_changed(str(current_user.id), str(device.id), new_status, db=self.db)

        return JSONResponse(
            content={
                "message": f"Applied preset '{preset['name']}' to '{device.name}'",
                "parameters": updated_parameters,
            },
            status_code=status.HTTP_200_OK
        )
