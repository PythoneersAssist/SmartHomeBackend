from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi_utils.cbv import cbv
from sqlalchemy.orm import Session
from typing import Annotated


router = APIRouter(prefix="/devices")

@cbv(router)
class DeviceEndpoints:
    @router.post("/create", tags=["device"])
    def create_device():
        pass

    @router.post("/get", tags=["device"])
    def get_registered_devices():
        pass

    @router.post("/get_id", tags=["device"])
    def get_registered_device_by_id():
        pass

    @router.post("/update", tags=["device"])
    def update_registered_device_by_id():
        pass

    @router.post("/delete", tags=["device"])
    def delete_device_by_id():
        pass

