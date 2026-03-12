from pydantic import BaseModel
from database.enums import AutomationTriggerType
from uuid import UUID

class CreateAutomationModel(BaseModel):
    name: str
    trigger_type: AutomationTriggerType
    trigger_value: str | None = None
    execution_day: int | None = None
    device_id: UUID

class UpdateAutomationModel(BaseModel):
    automation_id: UUID
    name: str | None = None
    trigger_type: AutomationTriggerType | None = None
    trigger_value: str | None = None
    execution_day: int | None = None
