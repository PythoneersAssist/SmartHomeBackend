from enum import Enum

class FloorType(str, Enum):
    ENTRANCE = "Entrance"
    FLOOR_1 = "1st"
    FLOOR_2 = "2nd"
    FLOOR_3 = "3rd"
    FLOOR_4 = "4th"
    FLOOR_5 = "5th"

class DeviceType(int, Enum):
    LIGHT = 0
    LED_STRIP = 1
    OUTLET = 2
    FANS = 3
    THERMOSTAT = 4
    AIR_CONDITIONER = 5
    HUMIDIFIER = 6
    HEATER = 7
    GARAGE_DOOR = 8
    GATE = 9
    TV = 10
    SPEAKER = 11
    OVEN = 12
    DISHWASHER = 13
    WASHER = 14
    DRYER = 15
    REFRIGERATOR = 16
    CURTAINS = 17
    ROUTER = 18
    HUB = 19
    OTHER = 20
    UNKNOWN = -1

class AutomationTriggerType(int, Enum):
    UNKNOWN = -1
    TIME = 0
    TEMPERATURE = 1
    LUX = 2