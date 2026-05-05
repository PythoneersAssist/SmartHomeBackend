"""
Tool definitions for AI function calling.
Defines all functions that the LLM has access to for controlling smart home devices.
Uses OpenAI-compatible tool format for Groq.
"""
from typing import Any


def get_gemini_tools() -> list[dict[str, Any]]:
    """Legacy alias kept for backward compatibility."""
    return get_groq_tools()


def get_groq_tools() -> list[dict[str, Any]]:
    """
    Returns the tool definitions for Groq/OpenAI-compatible function calling.

    Each tool is a dict with "type": "function" and a nested "function" key
    containing the name, description, and JSON Schema parameters.
    """
    return [
        {"type": "function", "function": {"name": "get_houses", "description": "Get all houses owned by the current user. Use this to see what houses are available.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "get_rooms", "description": "Get all rooms in a specific house.", "parameters": {"type": "object", "properties": {"house_id": {"type": "string", "description": "UUID of the house to get rooms from"}}, "required": ["house_id"]}}},
        {"type": "function", "function": {"name": "get_devices", "description": "Get all devices in a specific room or house. Returns device list with current status and parameters.", "parameters": {"type": "object", "properties": {"house_id": {"type": "string", "description": "UUID of the house"}, "room_id": {"type": "string", "description": "Optional: UUID of specific room. If not provided, returns all devices in house."}}, "required": ["house_id"]}}},
        {"type": "function", "function": {"name": "toggle_device", "description": "Turn a device on or off.", "parameters": {"type": "object", "properties": {"device_id": {"type": "string", "description": "UUID of the device to toggle"}, "turn_on": {"type": "boolean", "description": "True to turn on, False to turn off"}}, "required": ["device_id", "turn_on"]}}},
        {"type": "function", "function": {"name": "set_device_parameters", "description": "Set specific parameters on a device (e.g., brightness, temperature, volume).", "parameters": {"type": "object", "properties": {"device_id": {"type": "string", "description": "UUID of the device"}, "parameters": {"type": "object", "description": "Key-value pairs of parameters to set."}}, "required": ["device_id", "parameters"]}}},
        {"type": "function", "function": {"name": "create_time_automation", "description": "Create a time-based automation that triggers at a specific time (optionally on a specific day of week).", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Name for the automation (e.g., 'Morning lights')"}, "device_id": {"type": "string", "description": "UUID of the device to control"}, "trigger_value": {"type": "string", "description": "Time in HH:MM or HH:MM:SS format"}, "execution_day": {"type": "integer", "description": "Optional: Day of week (0=Monday...)"}, "turn_on": {"type": "boolean", "description": "True to turn device on at trigger time, False to turn off"}, "parameters": {"type": "object", "description": "Optional: Additional parameters to set when automation triggers"}}, "required": ["name", "device_id", "trigger_value"]}}},
        {"type": "function", "function": {"name": "create_temperature_automation", "description": "Create a temperature-based automation that triggers when ambient temperature exceeds a threshold.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Name for the automation"}, "device_id": {"type": "string", "description": "UUID of the device to control"}, "trigger_value": {"type": "string", "description": "Temperature threshold as string"}, "turn_on": {"type": "boolean", "description": "True to turn device on when triggered"}, "parameters": {"type": "object", "description": "Optional: Additional parameters"}}, "required": ["name", "device_id", "trigger_value"]}}},
        {"type": "function", "function": {"name": "create_light_automation", "description": "Create a light-based (lux) automation that triggers when ambient light exceeds a threshold.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Name for the automation"}, "device_id": {"type": "string", "description": "UUID of the device to control"}, "trigger_value": {"type": "string", "description": "Light threshold in lux as string"}, "turn_on": {"type": "boolean", "description": "True to turn device on when triggered"}, "parameters": {"type": "object", "description": "Optional: Additional parameters to set when triggered"}}, "required": ["name", "device_id", "trigger_value"]}}},
        {"type": "function", "function": {"name": "update_automation", "description": "Update an existing automation's settings.", "parameters": {"type": "object", "properties": {"automation_id": {"type": "string", "description": "UUID of the automation to update"}, "name": {"type": "string", "description": "Optional: New name for the automation"}, "trigger_value": {"type": "string", "description": "Optional: New trigger value"}, "turn_on": {"type": "boolean", "description": "Optional: New on/off state"}}, "required": ["automation_id"]}}},
        {"type": "function", "function": {"name": "delete_automation", "description": "Delete an automation.", "parameters": {"type": "object", "properties": {"automation_id": {"type": "string", "description": "UUID of the automation to delete"}}, "required": ["automation_id"]}}},
        {"type": "function", "function": {"name": "get_automations", "description": "Get all automations for a specific device.", "parameters": {"type": "object", "properties": {"device_id": {"type": "string", "description": "UUID of the device"}}, "required": ["device_id"]}}},
        {"type": "function", "function": {"name": "get_energy_status", "description": "Get current real-time energy consumption data for a house, room, or specific device.", "parameters": {"type": "object", "properties": {"house_id": {"type": "string", "description": "UUID of the house"}, "room_id": {"type": "string", "description": "Optional: UUID of room to limit query to that room"}, "device_id": {"type": "string", "description": "Optional: UUID of specific device"}}, "required": ["house_id"]}}},
        {"type": "function", "function": {"name": "find_device_by_name", "description": "Find a device by name in user's houses. Useful when user says 'turn on the lights in kitchen' but you need the device UUID.", "parameters": {"type": "object", "properties": {"device_name": {"type": "string", "description": "Name of the device to find"}, "house_id": {"type": "string", "description": "Optional: Limit search to specific house UUID"}}, "required": ["device_name"]}}},
    ]
