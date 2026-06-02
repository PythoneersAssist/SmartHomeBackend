from pydantic import BaseModel
from uuid import UUID


class ApplyPresetModel(BaseModel):
    device_id: UUID
    preset_id: str
