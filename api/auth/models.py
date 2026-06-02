from pydantic import BaseModel

class TokenData(BaseModel):
    id: str | None = None
    username: str | None = None

class ForgotPasswordModel(BaseModel):
    email: str

class ResetPasswordModel(BaseModel):
    token: str
    new_password: str
