from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from database.database import get_db
from database.models import User, House, Room, Device, Automation
from api.automations.models import CreateAutomationModel, UpdateAutomationModel
from api.automations.scheduler import parse_time_trigger
from api.auth.endpoints import get_current_user
from api.notifications.ws_manager import notify_automation_changed
from database.enums import AutomationTriggerType

router = APIRouter(prefix="/automations")

@cbv(router)
class AutomationEndpoints:
    db: Session = Depends(get_db)

    def _verify_device_ownership(self, device: Device, user: User):
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

    @router.post("/create", tags=["automation"])
    def create_automation(self, data: CreateAutomationModel, current_user: Annotated[User, Depends(get_current_user)]):
        device = self.db.query(Device).filter(Device.id == data.device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        self._verify_device_ownership(device, current_user)

        automation = Automation(
            name=data.name,
            trigger_type=data.trigger_type,
            trigger_value=data.trigger_value,
            execution_day=data.execution_day,
            device=device,
        )
        self.db.add(automation)
        self.db.commit()

        notify_automation_changed(
            str(current_user.id),
            action="created",
            automation_id=str(automation.id),
            automation_name=automation.name,
        )

        return JSONResponse(
            content={"message": f"Automation '{data.name}' created successfully"},
            status_code=status.HTTP_200_OK
        )

    @router.get("/get", tags=["automation"])
    def get_all_registered_automations(self, current_user: Annotated[User, Depends(get_current_user)]):
        automations = (
            self.db.query(Automation)
            .join(Device, Automation.device_id == Device.id)
            .join(Room, Device.room_id == Room.id)
            .join(House, Room.house_id == House.id)
            .filter(House.user_id == current_user.id)
            .all()
        )

        data = []
        for auto in automations:
            data.append({
                "id": str(auto.id),
                "name": auto.name,
                "trigger_type": auto.trigger_type.value if auto.trigger_type is not None else None,
                "trigger_value": auto.trigger_value,
                "execution_day": auto.execution_day,
                "device_id": str(auto.device_id),
            })

        return JSONResponse(
            content={"message": f"Retrieved {len(data)} automations", "automations": data},
            status_code=status.HTTP_200_OK
        )

    @router.get("/get_id/{automation_id}", tags=["automation"])
    def get_automation_by_id(self, automation_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        automation = self.db.query(Automation).filter(Automation.id == automation_id).first()
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )

        device = self.db.query(Device).filter(Device.id == automation.device_id).first()
        self._verify_device_ownership(device, current_user)

        data = {
            "id": str(automation.id),
            "name": automation.name,
            "trigger_type": automation.trigger_type.value if automation.trigger_type is not None else None,
            "trigger_value": automation.trigger_value,
            "execution_day": automation.execution_day,
            "device_id": str(automation.device_id),
        }

        return JSONResponse(
            content={"message": f"Automation '{automation.name}' retrieved successfully", "automation": data},
            status_code=status.HTTP_200_OK
        )

    @router.put("/update", tags=["automation"])
    def update_automation(self, data: UpdateAutomationModel, current_user: Annotated[User, Depends(get_current_user)]):
        automation = self.db.query(Automation).filter(Automation.id == data.automation_id).first()
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )

        device = self.db.query(Device).filter(Device.id == automation.device_id).first()
        self._verify_device_ownership(device, current_user)

        if data.name is not None:
            automation.name = data.name
        if data.trigger_type is not None:
            automation.trigger_type = data.trigger_type
        if data.trigger_value is not None:
            automation.trigger_value = data.trigger_value
        if data.execution_day is not None:
            automation.execution_day = data.execution_day

        if automation.trigger_type == AutomationTriggerType.TIME and parse_time_trigger(automation.trigger_value) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time automations require trigger_value in HH:MM or HH:MM:SS format"
            )

        self.db.commit()

        notify_automation_changed(
            str(current_user.id),
            action="updated",
            automation_id=str(automation.id),
            automation_name=automation.name,
        )

        return JSONResponse(
            content={"message": f"Automation '{automation.name}' updated successfully"},
            status_code=status.HTTP_200_OK
        )

    @router.delete("/delete/{automation_id}", tags=["automation"])
    def delete_automation(self, automation_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        automation = self.db.query(Automation).filter(Automation.id == automation_id).first()
        if not automation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Automation not found"
            )

        device = self.db.query(Device).filter(Device.id == automation.device_id).first()
        self._verify_device_ownership(device, current_user)

        automation_name = automation.name
        self.db.delete(automation)
        self.db.commit()

        notify_automation_changed(
            str(current_user.id),
            action="deleted",
            automation_id=str(automation_id),
            automation_name=automation_name,
        )

        return JSONResponse(
            content={"message": f"Automation '{automation_name}' deleted successfully"},
            status_code=status.HTTP_200_OK
        )
