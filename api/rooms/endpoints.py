from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from database.database import get_db
from database.models import User, House, Room, Device
from database.enums import RoomType
from api.rooms.models import CreateRoomModel, UpdateRoomModel
from api.auth.endpoints import get_current_user

router = APIRouter(prefix="/rooms")

@cbv(router)
class RoomEndpoints:
    db: Session = Depends(get_db)

    def _verify_room_ownership(self, room: Room, user: User) -> House:
        house = self.db.query(House).filter(
            House.id == room.house_id,
            House.user_id == user.id
        ).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room"
            )
        return house

    @router.post("/create", tags=["room"])
    def create_room(self, data: CreateRoomModel, current_user: Annotated[User, Depends(get_current_user)]):
        house = self.db.query(House).filter(House.id == data.house_id).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="House not found"
            )

        if house.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this house"
            )

        if self.db.query(Room).filter(Room.house_id == data.house_id, Room.name == data.name).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A room with name '{data.name}' already exists in this house"
            )

        self.db.add(Room(
            name=data.name,
            floor=data.floor,
            room_type=data.room_type,
            house=house
        ))
        self.db.commit()

        return JSONResponse(
            content={"message": f"Room '{data.name}' created successfully"},
            status_code=status.HTTP_200_OK
        )

    @router.get("/get_by_house_id/{house_id}", tags=["room"])
    def get_rooms_from_house(self, house_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        house = self.db.query(House).filter(House.id == house_id).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="House not found"
            )

        if house.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this house"
            )

        rooms = self.db.query(Room).filter(Room.house_id == house_id).all()

        data = []
        for room in rooms:
            data.append({
                "id": str(room.id),
                "name": room.name,
                "floor": room.floor.value if room.floor is not None else None,
                "room_type": room.room_type.value if room.room_type is not None else RoomType.OTHER.value,
                "house_id": str(room.house_id)
            })

        return JSONResponse(
            content={"message": f"Retrieved {len(data)} rooms from house '{house.name}'", "rooms": data},
            status_code=status.HTTP_200_OK
        )

    @router.get("/get_by_room_id/{room_id}", tags=["room"])
    def get_room_by_id(self, room_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        room = self.db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        self._verify_room_ownership(room, current_user)

        devices = self.db.query(Device).filter(Device.room_id == room.id).all()

        data = {
            "id": str(room.id),
            "name": room.name,
            "floor": room.floor.value if room.floor is not None else None,
            "room_type": room.room_type.value if room.room_type is not None else RoomType.OTHER.value,
            "house_id": str(room.house_id),
            "devices": []
        }

        for device in devices:
            data["devices"].append({
                "id": str(device.id),
                "name": device.name,
                "type": device.type.value if device.type is not None else None,
                "parameters": device.parameters
            })

        return JSONResponse(
            content={"message": f"Retrieved {len(data['devices'])} devices from room '{data['name']}'", "room": data}, status_code=status.HTTP_200_OK
        )

    @router.put("/update", tags=["room"])
    def update_room_by_id(self, data: UpdateRoomModel, current_user: Annotated[User, Depends(get_current_user)]):
        room = self.db.query(Room).filter(Room.id == data.room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        self._verify_room_ownership(room, current_user)

        if data.name:
            existing = self.db.query(Room).filter(
                Room.house_id == room.house_id,
                Room.name == data.name,
                Room.id != room.id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A room with that name already exists in this house"
                )
            room.name = data.name

        if data.floor is not None:
            room.floor = data.floor

        if data.room_type is not None:
            room.room_type = data.room_type

        self.db.commit()

        return JSONResponse(
            content={"message": f"Room '{room.name}' updated successfully"},
            status_code=status.HTTP_200_OK
        )

    @router.delete("/delete/{room_id}", tags=["room"])
    def delete_room_by_id(self, room_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        room = self.db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        self._verify_room_ownership(room, current_user)

        self.db.delete(room)
        self.db.commit()

        return JSONResponse(
            content={"message": f"Room '{room.name}' deleted successfully"},
            status_code=status.HTTP_200_OK
        )