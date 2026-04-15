from pydantic import BaseModel
from database.enums import FloorType, RoomType
from uuid import UUID

class CreateRoomModel(BaseModel):
    name: str
    floor: FloorType
    room_type: RoomType = RoomType.OTHER
    house_id: UUID

class UpdateRoomModel(BaseModel):
    room_id: UUID
    name: str | None = None
    floor: FloorType | None = None
    room_type: RoomType | None = None
