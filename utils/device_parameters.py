DEFAULT_DEVICE = {
    "status" : False
}

LED_DEVICE = {
    "status" : False,
    "rgb" : [255,255,255]
}

FAN_DEVICE = {
    "status" : False,
    "fan_power" : 0.0 #0-100
}

THERMOSTAT_DEVICE = {
    "status" : False,
    "temperature" : 21.0
}

AIR_CONDITIONER_DEVICE = {
    "status": False,
    "setting": 0, # hot/cold
    "target_temperature": 21.0
}

HEATER_DEVICE = {
    "status": False,
    "target_temperature": 21.0,
    "power": 0 # 0 - 100
}

TV_DEVICE = {
    "status": False,
    "volume": 0, #0-100
}

SPEAKER_DEVICE = {
    "status": False,
    "volume": 0,
}

OVEN_DEVICE = {
    "status": False,
    "power_setting": 0,
    "target_temperature": 180.0
}

WASHER_AND_DRIER_DEVICE = {
    "status": False,
    "wash_type": 0, 
}

REFRIGERATOR_DEVICE = {
    "status": False,
    "power": 0
}

