from database.database import Base
from database.enums import FloorType, DeviceType, AutomationTriggerType
from utils import device_parameters

from sqlalchemy import Column, Integer, String, Boolean, UUID, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from uuid import uuid4

class User(Base):
    __tablename__ = "users"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable= False)
    username = Column(String, nullable = False)
    email = Column(String, nullable = False)
    password = Column(String, nullable = False)
    registered_at = Column(String, default = 0, nullable = False)
    households = relationship("House", back_populates="user")

class House(Base):
    __tablename__ = "houses"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    description = Column(String, default = "No description provided")

    user_id = Column(UUID, ForeignKey("users.id"), nullable = False)

    user = relationship("User", back_populates="households")
    rooms = relationship("Room", back_populates="house")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    floor = Column(Enum(FloorType), default = "No description provided")

    house_id = Column(UUID, ForeignKey("houses.id"), nullable = False)

    house = relationship("House", back_populates="rooms")
    devices = relationship("Device", back_populates="room")

class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    type = Column(Enum(DeviceType), default=DeviceType.UNKNOWN)
    parameters = Column(JSON, default=device_parameters.DEFAULT_DEVICE, nullable=False)

    room_id = Column(UUID, ForeignKey("rooms.id"), nullable = False)
    room = relationship("Room", back_populates="devices")
    automation = relationship("Automation", back_populates="device")

class Automation(Base):
    __tablename__ = "automations"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)

    trigger_type = Column(Enum(AutomationTriggerType), default = AutomationTriggerType.UNKNOWN, nullable = False)
    trigger_value = Column(Enum(AutomationTriggerType), default = AutomationTriggerType.UNKNOWN, nullable = False)

    execution_day = Column(Integer, default=None)
    
    device_id = Column(UUID, ForeignKey("devices.id"), nullable = False)
    device = relationship("Device", back_populates="automation")
