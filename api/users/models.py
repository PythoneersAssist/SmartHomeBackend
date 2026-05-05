from pydantic import BaseModel
from typing import Optional

class CreateUserModel(BaseModel):
    username: str
    email: str
    password: str

class UpdateUserModel(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None