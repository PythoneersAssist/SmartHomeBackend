from datetime import datetime

from pydantic import BaseModel, model_validator
from database.enums import AutomationTriggerType
from uuid import UUID


def _is_valid_time_value(value: str) -> bool:
    normalized = value.strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            datetime.strptime(normalized, fmt)
            return True
        except ValueError:
            continue
    return False

class CreateAutomationModel(BaseModel):
    name: str
    trigger_type: AutomationTriggerType
    trigger_value: str | None = None
    execution_day: int | None = None
    device_id: UUID

    @model_validator(mode="after")
    def validate_time_trigger_fields(self):
        if self.execution_day is not None and not 0 <= self.execution_day <= 6:
            raise ValueError("execution_day must be between 0 (Monday) and 6 (Sunday)")

        if self.trigger_type == AutomationTriggerType.TIME:
            if self.trigger_value is None or not _is_valid_time_value(self.trigger_value):
                raise ValueError("Time automations require trigger_value in HH:MM or HH:MM:SS format")

        return self

class UpdateAutomationModel(BaseModel):
    automation_id: UUID
    name: str | None = None
    trigger_type: AutomationTriggerType | None = None
    trigger_value: str | None = None
    execution_day: int | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        if self.execution_day is not None and not 0 <= self.execution_day <= 6:
            raise ValueError("execution_day must be between 0 (Monday) and 6 (Sunday)")

        if self.trigger_type == AutomationTriggerType.TIME and self.trigger_value is not None:
            if not _is_valid_time_value(self.trigger_value):
                raise ValueError("Time automations require trigger_value in HH:MM or HH:MM:SS format")

        return self
