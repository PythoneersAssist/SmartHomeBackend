from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.enums import AutomationTriggerType, DeviceType
from database.models import Automation, Device, Room


# Device types that can act as the ambient sensor for each threshold trigger.
# A threshold automation should only fire when the house actually contains a
# device capable of producing the relevant reading.
TRIGGER_SENSOR_DEVICE_TYPES: dict[AutomationTriggerType, tuple[DeviceType, ...]] = {
    AutomationTriggerType.TEMPERATURE: (DeviceType.THERMOSTAT,),
    AutomationTriggerType.LUX: (DeviceType.LIGHT, DeviceType.LED_STRIP),
}


def house_supports_trigger(db: Session, house_id: UUID, trigger_type: AutomationTriggerType) -> bool:
    """Return True if the house has a device that can drive the given trigger.

    Temperature automations require a thermostat in the house; light (lux)
    automations require at least one light or LED strip. Non-threshold triggers
    (e.g. TIME) are always supported.
    """
    required_types = TRIGGER_SENSOR_DEVICE_TYPES.get(trigger_type)
    if not required_types:
        return True

    exists = (
        db.query(Device.id)
        .join(Room, Device.room_id == Room.id)
        .filter(Room.house_id == house_id, Device.type.in_(required_types))
        .first()
    )
    return exists is not None


def _is_threshold_met(current_value: Any, trigger_value: Any) -> bool:
    try:
        current = float(current_value)
        threshold = float(trigger_value)
    except (TypeError, ValueError):
        return False

    return current >= threshold


def should_emit_threshold_automation_trigger(automation: Automation, parameters: dict[str, Any]) -> bool:
    if automation.trigger_type == AutomationTriggerType.TEMPERATURE:
        return _is_threshold_met(parameters.get("temperature"), automation.trigger_value)
    if automation.trigger_type == AutomationTriggerType.LUX:
        return _is_threshold_met(parameters.get("lux"), automation.trigger_value)
    return False


def execute_automation_device_action(
    device: Device,
    turn_on: bool = True,
    parameter_updates: dict[str, Any] | None = None,
) -> bool:
    original_parameters = dict(device.parameters or {})
    current_parameters = dict(original_parameters)

    if parameter_updates:
        current_parameters.update(parameter_updates)

    desired_status = bool(turn_on)
    current_parameters["status"] = desired_status

    if current_parameters == original_parameters:
        return False

    device.parameters = current_parameters
    return True
