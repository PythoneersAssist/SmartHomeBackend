from database.database import Base
from database.models import FloorType

from sqlalchemy import Column, Integer, String, Boolean, UUID, ForeignKey, relationship, Enum
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

    id = Column(UUID, default=uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    description = Column(String, default="No description provided")

    user_id = Column(UUID, ForeignKey("users.id"), nullable = False)

    user = relationship("users", back_populates="households")
    rooms = relationship("rooms", back_populates="house")

class Rooms(Base):
    __tablename__ = "rooms"

    id = Column(UUID, default=uuid4, primary_key = True, index = True, nullable = False)
    name = Column(String, nullable = False)
    floor = Column(Enum(FloorType), default="No description provided")

    house_id = Column(UUID, ForeignKey("houses.id"), nullable = False)
    house = relationship("users", back_populates="rooms")

class Devices(Base):
    pass

class Automations(Base):
    pass