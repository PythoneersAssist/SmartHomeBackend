from typing import Any

from database.enums import AutomationTriggerType
from database.models import Automation, Device


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
