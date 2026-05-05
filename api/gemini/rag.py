"""
RAG (Retrieval-Augmented Generation) support for Gemini.
Provides device documentation and smart home context to enhance AI responses.
"""
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.models import User, Device, Room, House


logger = logging.getLogger(__name__)


class RAGContext:
    """Retrieval-Augmented Generation context for smart home devices."""
    
    # Device documentation/specifications
    DEVICE_DOCUMENTATION = {
        "Light": {
            "description": "Smart light bulb or LED fixture",
            "parameters": {
                "status": "Boolean (on/off)",
                "brightness": "0-100 (percentage)",
                "rgb": "List [R, G, B] for color lights (0-255 each)",
            },
            "common_operations": [
                "Turn on/off",
                "Set brightness (e.g., 'set brightness to 80%')",
                "Change color (RGB values for color lights)",
                "Create time-based automation",
            ],
        },
        "LED_STRIP": {
            "description": "Smart LED strip for ambient lighting",
            "parameters": {
                "status": "Boolean (on/off)",
                "brightness": "0-100 (percentage)",
                "rgb": "List [R, G, B] (0-255 each)",
            },
            "common_operations": [
                "Turn on/off",
                "Set brightness and color",
                "Create automation based on time or ambient light",
            ],
        },
        "THERMOSTAT": {
            "description": "Smart thermostat for temperature control",
            "parameters": {
                "status": "Boolean (on/off)",
                "temperature": "Current room temperature in Celsius",
            },
            "common_operations": [
                "Check current temperature",
                "Create temperature-based automations",
                "View energy consumption",
            ],
        },
        "AC": {
            "description": "Air conditioning unit",
            "parameters": {
                "status": "Boolean (on/off)",
                "setting": "String (hot/cold/dry)",
                "target_temperature": "Desired temperature in Celsius",
            },
            "common_operations": [
                "Turn on/off",
                "Set target temperature",
                "Change mode (hot/cold/dry)",
                "Create temperature-based automation",
            ],
        },
        "HEATER": {
            "description": "Space heater",
            "parameters": {
                "status": "Boolean (on/off)",
                "target_temperature": "Desired temperature in Celsius",
            },
            "common_operations": [
                "Turn on/off",
                "Set target temperature",
                "Create temperature-based automation",
            ],
        },
        "FAN": {
            "description": "Ceiling or portable fan",
            "parameters": {
                "status": "Boolean (on/off)",
                "speed": "0-100 (percentage)",
            },
            "common_operations": [
                "Turn on/off",
                "Adjust speed",
                "Create automation",
            ],
        },
        "TV": {
            "description": "Smart television",
            "parameters": {
                "status": "Boolean (on/off)",
                "volume": "0-100 (percentage)",
                "channel": "Integer channel number",
            },
            "common_operations": [
                "Turn on/off",
                "Adjust volume",
                "Change channel",
            ],
        },
        "SPEAKER": {
            "description": "Smart speaker or audio device",
            "parameters": {
                "status": "Boolean (on/off)",
                "volume": "0-100 (percentage)",
            },
            "common_operations": [
                "Turn on/off",
                "Adjust volume",
                "Create audio-triggered automation",
            ],
        },
        "OVEN": {
            "description": "Smart oven",
            "parameters": {
                "status": "Boolean (on/off)",
                "power_setting": "Power level percentage",
                "target_temperature": "Desired temperature in Celsius",
            },
            "common_operations": [
                "Turn on/off",
                "Set power level and temperature",
            ],
        },
        "DISHWASHER": {
            "description": "Smart dishwasher",
            "parameters": {
                "status": "Boolean (on/off)",
                "cycle": "Wash cycle type",
            },
            "common_operations": [
                "Turn on/off",
                "Select wash cycle",
                "Create time-based automation",
            ],
        },
        "WASHER": {
            "description": "Smart washing machine",
            "parameters": {
                "status": "Boolean (on/off)",
                "wash_type": "Wash cycle type",
            },
            "common_operations": [
                "Turn on/off",
                "Select wash type",
                "Create automation",
            ],
        },
        "DRYER": {
            "description": "Smart clothes dryer",
            "parameters": {
                "status": "Boolean (on/off)",
                "heat_setting": "Heat level",
            },
            "common_operations": [
                "Turn on/off",
                "Adjust heat setting",
                "Create automation",
            ],
        },
        "REFRIGERATOR": {
            "description": "Smart refrigerator",
            "parameters": {
                "status": "Boolean (on/off)",
            },
            "common_operations": [
                "Monitor status",
                "View energy consumption",
            ],
        },
        "GARAGE_DOOR": {
            "description": "Smart garage door opener",
            "parameters": {
                "status": "Boolean (open/closed)",
            },
            "common_operations": [
                "Open/close garage door",
                "Create time-based automation",
            ],
        },
        "GATE": {
            "description": "Smart gate opener",
            "parameters": {
                "status": "Boolean (open/closed)",
            },
            "common_operations": [
                "Open/close gate",
                "Create automation",
            ],
        },
        "CURTAINS": {
            "description": "Smart motorized curtains",
            "parameters": {
                "status": "Boolean (open/closed)",
                "position": "0-100 (percentage open)",
            },
            "common_operations": [
                "Open/close curtains",
                "Set position",
                "Create light-based automation",
            ],
        },
        "HUMIDIFIER": {
            "description": "Smart humidifier",
            "parameters": {
                "status": "Boolean (on/off)",
                "humidity_level": "Target humidity percentage",
            },
            "common_operations": [
                "Turn on/off",
                "Set target humidity",
            ],
        },
        "ROUTER": {
            "description": "Smart WiFi router",
            "parameters": {
                "status": "Boolean (on/off)",
            },
            "common_operations": [
                "Monitor connectivity",
                "View network status",
            ],
        },
        "HUB": {
            "description": "Smart home hub/bridge",
            "parameters": {
                "status": "Boolean (on/off)",
            },
            "common_operations": [
                "Monitor hub status",
                "Ensure connectivity to devices",
            ],
        },
        "OUTLET": {
            "description": "Smart power outlet/plug",
            "parameters": {
                "status": "Boolean (on/off)",
            },
            "common_operations": [
                "Turn plugged devices on/off",
                "Monitor power consumption",
            ],
        },
    }
    
    @staticmethod
    def get_device_documentation(device_type: str) -> Optional[dict]:
        """Get documentation for a specific device type."""
        return RAGContext.DEVICE_DOCUMENTATION.get(device_type)
    
    @staticmethod
    def get_user_context(user_id: UUID, db: Session) -> str:
        """
        Generate RAG context about the user's smart home setup.
        Includes device inventory, automations, and energy patterns.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return ""
        
        houses = db.query(House).filter(House.user_id == user_id).all()
        
        context = f"\\n=== Smart Home Context for {user.username} ===\\n"
        
        for house in houses:
            context += f"\\nHouse: {house.name}\\n"
            
            rooms = db.query(Room).filter(Room.house_id == house.id).all()
            for room in rooms:
                devices = db.query(Device).filter(Device.room_id == room.id).all()
                
                if devices:
                    context += f"  {room.name}:\\n"
                    for device in devices:
                        status = "ON" if device.status else "OFF"
                        context += f"    - {device.name} ({device.device_type}): {status}\\n"
        
        return context
    
    @staticmethod
    def get_energy_context(user_id: UUID, db: Session) -> str:
        """
        Generate RAG context about energy consumption patterns.
        """
        houses = db.query(House).filter(House.user_id == user_id).all()
        
        context = "\\n=== Energy Consumption Summary ===\\n"
        
        for house in houses:
            # In a real scenario, you'd aggregate energy usage from EnergyHistory
            context += f"House: {house.name}\\n"
            context += "  (Energy data available via get_energy_status function)\\n"
        
        return context
