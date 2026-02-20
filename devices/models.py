from pydantic import BaseModel
from database.enums import DeviceType
from uuid import UUID

class CreateDeviceModel(BaseModel):
    name: str
    _type: DeviceType
    parameters: dict
    room_id: UUID