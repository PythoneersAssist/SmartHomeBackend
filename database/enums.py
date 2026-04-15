from enum import Enum

class FloorType(str, Enum):
    ENTRANCE = "Entrance"
    FLOOR_1 = "1st"
    FLOOR_2 = "2nd"
    FLOOR_3 = "3rd"
    FLOOR_4 = "4th"
    FLOOR_5 = "5th"


class RoomType(str, Enum):
    # Core Rooms
    LIVING_ROOM = "living_room"
    KITCHEN = "kitchen"
    MASTER_BEDROOM = "master_bedroom"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    DINING_ROOM = "dining_room"
    ENTRANCE_HALLWAY = "entrance_hallway"

    # Work & Storage
    HOME_OFFICE = "home_office"
    LIBRARY = "library"
    LAUNDRY_ROOM = "laundry_room"
    GARAGE = "garage"
    STORAGE_ROOM = "storage_room"
    BASEMENT = "basement"
    ATTIC = "attic"

    # Leisure
    GYM = "gym"
    HOME_THEATER = "home_theater"
    GAME_ROOM = "game_room"
    BALCONY = "balcony"
    TERRACE = "terrace"

    # Outdoor
    GARDEN = "garden"
    BACKYARD = "backyard"
    POOL_AREA = "pool_area"

    OTHER = "other"

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