"""
Built-in device presets.

A read-only catalog of brand/device presets a user can apply to a device.
Each preset targets a device type (see database.enums.DeviceType) and carries a
set of parameter values. Applying a preset merges these values into the
device's current parameters, so unrelated keys are preserved.
"""
from database.enums import DeviceType


# Each preset:
#   id           - stable slug used by the API
#   name         - human friendly label
#   brand        - manufacturer / family the preset is modelled on
#   device_type  - DeviceType the preset applies to
#   description  - short explanation
#   parameters   - parameter values merged into the device when applied
DEVICE_PRESETS: list[dict] = [
    # ---- Samsung TV ----
    {
        "id": "samsung-tv-movie",
        "name": "Samsung TV - Movie Mode",
        "brand": "Samsung",
        "device_type": DeviceType.TV,
        "description": "Dimmed, cinematic volume for watching films.",
        "parameters": {"status": True, "volume": 25, "picture_mode": "movie"},
    },
    {
        "id": "samsung-tv-gaming",
        "name": "Samsung TV - Gaming Mode",
        "brand": "Samsung",
        "device_type": DeviceType.TV,
        "description": "Low-latency game mode with punchy volume.",
        "parameters": {"status": True, "volume": 40, "picture_mode": "game"},
    },
    {
        "id": "samsung-tv-sports",
        "name": "Samsung TV - Sports Mode",
        "brand": "Samsung",
        "device_type": DeviceType.TV,
        "description": "Bright, vivid picture and loud volume for live sports.",
        "parameters": {"status": True, "volume": 50, "picture_mode": "sports"},
    },
    {
        "id": "samsung-tv-night",
        "name": "Samsung TV - Night Mode",
        "brand": "Samsung",
        "device_type": DeviceType.TV,
        "description": "Quiet late-night viewing.",
        "parameters": {"status": True, "volume": 10, "picture_mode": "movie"},
    },
    # ---- Lighting ----
    {
        "id": "light-relax",
        "name": "Relax Lighting",
        "brand": "Generic",
        "device_type": DeviceType.LIGHT,
        "description": "Warm, dim light for relaxing.",
        "parameters": {"status": True, "brightness": 30},
    },
    {
        "id": "light-focus",
        "name": "Focus Lighting",
        "brand": "Generic",
        "device_type": DeviceType.LIGHT,
        "description": "Bright light for working or reading.",
        "parameters": {"status": True, "brightness": 100},
    },
    {
        "id": "ledstrip-movie",
        "name": "LED Strip - Movie Ambient",
        "brand": "Generic",
        "device_type": DeviceType.LED_STRIP,
        "description": "Soft blue bias lighting behind the TV.",
        "parameters": {"status": True, "rgb": [40, 60, 180]},
    },
    # ---- Climate ----
    {
        "id": "ac-eco-cool",
        "name": "AC - Eco Cool",
        "brand": "Generic",
        "device_type": DeviceType.AIR_CONDITIONER,
        "description": "Energy efficient cooling at 24°C.",
        "parameters": {"status": True, "setting": 1, "target_temperature": 24.0},
    },
    {
        "id": "heater-cozy",
        "name": "Heater - Cozy",
        "brand": "Generic",
        "device_type": DeviceType.HEATER,
        "description": "Comfortable warmth at 23°C.",
        "parameters": {"status": True, "target_temperature": 23.0, "power": 60},
    },
    # ---- Audio ----
    {
        "id": "speaker-party",
        "name": "Speaker - Party",
        "brand": "Generic",
        "device_type": DeviceType.SPEAKER,
        "description": "Loud volume for gatherings.",
        "parameters": {"status": True, "volume": 80},
    },
]

_PRESETS_BY_ID = {preset["id"]: preset for preset in DEVICE_PRESETS}


def serialize_preset(preset: dict) -> dict:
    """Return a JSON-serialisable view of a preset (DeviceType -> int)."""
    return {
        "id": preset["id"],
        "name": preset["name"],
        "brand": preset["brand"],
        "device_type": preset["device_type"].value,
        "description": preset["description"],
        "parameters": preset["parameters"],
    }


def get_preset(preset_id: str) -> dict | None:
    """Look up a preset by its id."""
    return _PRESETS_BY_ID.get(preset_id)


def list_presets(device_type: DeviceType | None = None) -> list[dict]:
    """List presets, optionally filtered to a single device type."""
    if device_type is None:
        return list(DEVICE_PRESETS)
    return [preset for preset in DEVICE_PRESETS if preset["device_type"] == device_type]
