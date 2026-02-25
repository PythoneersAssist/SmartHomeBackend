from pydantic import BaseModel
from database.enums import FloorType
from uuid import UUID

class CreateRoomModel(BaseModel):
    name: str
    floor: FloorType
    house_id: UUID

class UpdateRoomModel(BaseModel):
    room_id: UUID
    name: str | None = None
    floor: FloorType | None = None
