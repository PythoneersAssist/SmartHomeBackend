from database.database import Base
from database.models import FloorType, DeviceType, AutomationTriggerType
from utils import device_parameters

from sqlalchemy import Column, Integer, String, Boolean, UUID, ForeignKey, relationship, Enum, JSON
from uuid import uuid4

class Users(Base):
    __tablename__ = "users"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable= False)
    username = Column(String, nullable = False)
    email = Column(String, nullable = False)
    password = Column(String, nullable = False)
    registered_at = Column(Integer, default = 0, nullable = False)
    households = relationship("house", back_populates="user")

class House(Base):
    __tablename__ = "houses"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    description = Column(String, default = "No description provided")

    user_id = Column(UUID, ForeignKey("users.id"), nullable = False)

    user = relationship("users", back_populates="households")
    rooms = relationship("rooms", back_populates="house")

class Rooms(Base):
    __tablename__ = "rooms"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    floor = Column(Enum(FloorType), default = "No description provided")

    house_id = Column(UUID, ForeignKey("houses.id"), nullable = False)

    house = relationship("users", back_populates="rooms")
    devices = relationship("devices", back_populates="room")

class Devices(Base):
    __tablename__ = "devices"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    type = Column(Enum(DeviceType), default=Devices.UNKNOWN)
    parameters = Column(JSON, default=device_parameters.DEFAULT_DEVICE)

    room_id = Column(UUID, ForeignKey("rooms.id"), nullable = False)
    room = relationship("rooms", back_populates="devices")
    automation = relationship("automations", back_populates="device")

class Automations(Base):
    __tablename__ = "automations"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)

    trigger_type = Column(Enum(AutomationTriggerType), default = AutomationTriggerType.UNKNOWN, nullable = False)
    trigger_value = Column(Enum(AutomationTriggerType), default = AutomationTriggerType.UNKNOWN, nullable = False)

    execution_day = Column(Integer, default=None)
    
    device_id = Column(UUID, ForeignKey("devices.id"), nullable = False)
    device = relationship("devices", back_populates="automations")
