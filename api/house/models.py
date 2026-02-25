from pydantic import BaseModel
from uuid import UUID

class CreateHouseModel(BaseModel):
    name: str
    description: str | None = None

class UpdateHouseModel(BaseModel):
    house_id: UUID
    name: str | None = None
    description: str | None = None