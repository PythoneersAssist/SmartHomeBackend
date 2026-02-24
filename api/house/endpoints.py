from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from database.database import get_db
from database.models import User, House, Room
from api.house.models import CreateHouseModel, UpdateHouseModel
from api.auth.endpoints import get_current_user

router = APIRouter(prefix="/home")

@cbv(router)
class HouseEndpoints:
    db: Session = Depends(get_db)

    @router.post("/create", tags=["home"])
    def create_house(self, data: CreateHouseModel, current_user: Annotated[User, Depends(get_current_user)]):
        if self.db.query(House).filter(House.user_id == current_user.id, House.name == data.name).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You already have a house registered with name {data.name}"
            )

        self.db.add(House(
            name = data.name,
            description = data.description or "No description provided",
            user = current_user
        ))
        self.db.commit()

    @router.get("/get", tags=["home"])
    def get_registered_houses(self, current_user: Annotated[User, Depends(get_current_user)]):
        houses = self.db.query(House).filter(House.user == current_user).all()
        data = []

        for house in houses:
            data.append(
                {
                    "id" : str(house.id),
                    "name" : house.name,
                    "description" : house.description
                }
            )
        return JSONResponse(data, status_code=status.HTTP_200_OK)

    @router.get("/get_id/{house_id}", tags=["home"])
    def get_registered_house_by_id(self, house_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
        house = self.db.query(House).filter(House.id == house_id).first()
        if not house:
            return JSONResponse(content = [], status_code = status.HTTP_404_NOT_FOUND)
        rooms = self.db.query(Room).filter(Room.house == house).all()

        data = [
            {
                "id" : str(house.id),
                "name" : house.name,
                "description" : house.description
            },
            []
        ]
        
        for room in rooms:
            data[1].append(
                {
                    "room_id" : str(room.id),
                    "room_name" : room.name,
                    "room_floor" : room.floor,
                }
            )

        return JSONResponse(data, status_code = status.HTTP_200_OK)

    @router.put("/update", tags=["home"])
    def update_registered_house_by_id(self, data: UpdateHouseModel, current_user: Annotated[User, Depends(get_current_user)]):
        house = self.db.query(House).filter(House.id == data.house_id).first()


        if data.name:
            if self.db.query(House).filter(House.user_id == current_user.id, House.name == data.name).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You already have a house registered with that name"
                )
            house.name = data.name
        
        if data.description:
            house.description = data.description

        self.db.commit()

    @router.delete("/delete", tags=["home"])
    def delete_house_by_id(self):
        pass

