from database.database import Base
from database.enums import FloorType, RoomType, DeviceType, AutomationTriggerType
from utils import device_parameters

from sqlalchemy import Column, Integer, String, Boolean, UUID, ForeignKey, Enum, JSON, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from uuid import uuid4

class User(Base):
    __tablename__ = "users"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable= False)
    username = Column(String, nullable = False)
    email = Column(String, nullable = False)
    password = Column(String, nullable = False)
    registered_at = Column(String, default = 0, nullable = False)
    households = relationship("House", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

class House(Base):
    __tablename__ = "houses"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    description = Column(String, default = "No description provided")

    user_id = Column(UUID, ForeignKey("users.id"), nullable = False)

    user = relationship("User", back_populates="households")
    rooms = relationship("Room", back_populates="house", cascade="all, delete-orphan")
    energy_history = relationship("EnergyHistory", back_populates="house", cascade="all, delete-orphan")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    floor = Column(Enum(FloorType), default = FloorType.ENTRANCE)
    room_type = Column(Enum(RoomType), default = RoomType.OTHER, nullable = False)

    house_id = Column(UUID, ForeignKey("houses.id"), nullable = False)

    house = relationship("House", back_populates="rooms")
    devices = relationship("Device", back_populates="room", cascade="all, delete-orphan")
    energy_history = relationship("RoomEnergyHistory", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    type = Column(Enum(DeviceType), default=DeviceType.UNKNOWN)
    parameters = Column(JSON, default=device_parameters.DEFAULT_DEVICE, nullable=False)

    room_id = Column(UUID, ForeignKey("rooms.id"), nullable = False)
    room = relationship("Room", back_populates="devices")
    automation = relationship("Automation", back_populates="device", cascade="all, delete-orphan")
    energy_history = relationship("DeviceEnergyHistory", cascade="all, delete-orphan")

class Automation(Base):
    __tablename__ = "automations"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)

    trigger_type = Column(Enum(AutomationTriggerType), default = AutomationTriggerType.UNKNOWN, nullable = False)
    trigger_value = Column(String, nullable = True)
    turn_on = Column(Boolean, default = False, nullable = False)
    parameters = Column(JSON, nullable = True)

    execution_day = Column(Integer, default=None)
    
    device_id = Column(UUID, ForeignKey("devices.id"), nullable = False)
    device = relationship("Device", back_populates="automation")
    executions = relationship("AutomationExecution", back_populates="automation", cascade="all, delete-orphan")


class AutomationExecution(Base):
    __tablename__ = "automation_executions"
    __table_args__ = (
        UniqueConstraint("automation_id", "scheduled_for", name="uq_automation_execution_slot"),
    )

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    scheduled_for = Column(String, nullable = False)
    executed_at = Column(String, nullable = False)
    status = Column(String, default = "executed", nullable = False)
    error_message = Column(String, nullable = True)

    automation_id = Column(UUID, ForeignKey("automations.id"), nullable = False)
    automation = relationship("Automation", back_populates="executions")


class AutomationSchedulerState(Base):
    __tablename__ = "automation_scheduler_state"

    id = Column(Integer, primary_key = True, nullable = False)
    last_checked_at = Column(String, nullable = False)


class EnergyHistory(Base):
    __tablename__ = "energy_history"
    __table_args__ = (
        UniqueConstraint("house_id", "hour_slot", name="uq_energy_history_house_hour"),
    )

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    hour_slot = Column(String, nullable = False)
    total_estimated_watts = Column(Float, nullable = False)
    active_devices = Column(Integer, default = 0, nullable = False)
    total_devices = Column(Integer, default = 0, nullable = False)

    house_id = Column(UUID, ForeignKey("houses.id"), nullable = False)
    house = relationship("House", back_populates="energy_history")

class RoomEnergyHistory(Base):
    __tablename__ = "room_energy_history"
    __table_args__ = (
        UniqueConstraint("room_id", "hour_slot", name="uq_room_energy_history_room_hour"),
    )

    id = Column(UUID, default=uuid4, primary_key=True, index=True, nullable=False)
    hour_slot = Column(String, nullable=False)
    total_estimated_watts = Column(Float, nullable=False)
    active_devices = Column(Integer, default=0, nullable=False)
    total_devices = Column(Integer, default=0, nullable=False)

    room_id = Column(UUID, ForeignKey("rooms.id"), nullable=False)
    room = relationship("Room", back_populates="energy_history")


class DeviceEnergyHistory(Base):
    __tablename__ = "device_energy_history"
    __table_args__ = (
        UniqueConstraint("device_id", "hour_slot", name="uq_device_energy_history_device_hour"),
    )

    id = Column(UUID, default=uuid4, primary_key=True, index=True, nullable=False)
    hour_slot = Column(String, nullable=False)
    estimated_watts = Column(Float, nullable=False)
    is_on = Column(Boolean, default=False, nullable=False)

    device_id = Column(UUID, ForeignKey("devices.id"), nullable=False)
    device = relationship("Device", back_populates="energy_history")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID, default = uuid4, primary_key = True, index = True, nullable = False)
    title = Column(String, nullable = False)
    message = Column(String, nullable = False)
    is_read = Column(Boolean, default = False, nullable = False)
    created_at = Column(String, nullable = False)

    user_id = Column(UUID, ForeignKey("users.id"), nullable = False)
    user = relationship("User", back_populates="notifications")
