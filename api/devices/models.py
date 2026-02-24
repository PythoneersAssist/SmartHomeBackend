from pydantic import BaseModel
from database.enums import DeviceType
from uuid import UUID

class CreateDeviceModel(BaseModel):
    name: str
    device_type: DeviceType
    room_id: UUID

class UpdateDeviceModel(BaseModel):
    device_id: UUID
    name: str | None = None
    parameters: dict | None = None