from pydantic import BaseModel
from uuid import UUID

class CreateNotificationModel(BaseModel):
    title: str
    message: str

class UpdateNotificationModel(BaseModel):
    notification_id: UUID
    is_read: bool | None = None
