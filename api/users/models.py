from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class CreateUserModel(BaseModel):
    username: str
    email: str
    password: str

class UpdateUserModel(BaseModel):
    id: UUID
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None