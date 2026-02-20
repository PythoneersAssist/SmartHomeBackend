from pydantic import BaseModel
from database.enums import DeviceType
from uuid import UUID

class CreateHouseModel(BaseModel):
    name: str
    description: str | None = None

class UpdateHouseModel(BaseModel):
    house_id: UUID
    name: str | None
    description: str | None