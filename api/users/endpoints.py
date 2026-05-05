from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated

from database.database import get_db
from database.models import User

from api.auth.endpoints import get_current_user
from api.users.models import CreateUserModel, UpdateUserModel
from utils.validation import validate_email, validate_password
from utils.security import get_password_hash


router = APIRouter(prefix="/user")

@cbv(router)
class UserEndpoints:
    db: Session = Depends(get_db)

    @router.post("/create", tags=["user"])
    def create_user(self, data: CreateUserModel):

        if not validate_email(data.email):
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "Please enter a valid email."
                )

        if not validate_password(data.password):
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "Password must be between 8 and 72 characters, contain an uppercase letter, a lowercase letter, a number and a symbol."
                )

        if self.db.query(User).filter(User.email == data.email).first():
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "Email already in use."
                )

        self.db.add(User(
            username = data.username,
            email = data.email,
            password = get_password_hash(data.password),
            registered_at = datetime.now()
        ))
        self.db.commit()

        return JSONResponse(
            content = {
                "message" : "Account created successfully."
                },
            status_code = status.HTTP_200_OK
            )

    @router.patch("/update/", tags=["user"])
    def update_user(self, data: UpdateUserModel, current_user: Annotated[User, Depends(get_current_user)]):
        user = current_user

        if data.username:
            user.username = data.username

        if data.email:
            if not validate_email(data.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please enter a valid email."
                )
            
            existing_user = self.db.query(User).filter(User.email == data.email).first()
            if existing_user and existing_user.id != user.id:
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use."
                )
            user.email = data.email

        if data.password:
            if not validate_password(data.password):
                 raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be between 8 and 72 characters, contain an uppercase letter, a lowercase letter, a number and a symbol."
                )
            user.password = get_password_hash(data.password)

        self.db.commit()
        return JSONResponse(
            content = {
                "message" : "Account updated successfully."
                },
            status_code = status.HTTP_200_OK
            )

    @router.get("/get", tags=["user"])
    def get_user_details(self, current_user: Annotated[User, Depends(get_current_user)]):
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )
        return JSONResponse(
            content = {
                "id": str(current_user.id),
                "username": current_user.username,
                "email": current_user.email,
                "registered_at": str(current_user.registered_at)
            },
            status_code=status.HTTP_200_OK
        )

    @router.get("/get_devices", tags=["user"])
    def get_all_users_devices(self, current_user: Annotated[User, Depends(get_current_user)]):
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )
        
        data = {}
        for house in current_user.households:
            house_rooms = data.setdefault(house.name, {})
            for room in house.rooms:
                room_devices = []
                for device in room.devices:
                    room_devices.append({
                        "id": str(device.id),
                        "name": device.name,
                        "type": device.type.value if hasattr(device.type, "value") else str(device.type),
                        "room_id": str(device.room_id),
                        "room_name": room.name,
                        "house_id": str(house.id),
                        "house_name": house.name,
                        "parameters": device.parameters
                    })
                house_rooms[room.name] = room_devices
        
        return JSONResponse(
            content = data,
            status_code = status.HTTP_200_OK
        )