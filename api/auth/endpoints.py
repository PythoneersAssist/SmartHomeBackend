from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from os import getenv
from sqlalchemy.orm import Session
from typing import Annotated
from uuid import UUID

from api.auth.models import TokenData, ForgotPasswordModel, ResetPasswordModel
from database.database import get_db
from database.models import User
from utils.security import (
    verify_password,
    create_access_token,
    create_purposed_token,
    verify_purposed_token,
    get_password_hash,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from utils.validation import validate_password
from utils.email import send_email


router = APIRouter(tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

PASSWORD_RESET_PURPOSE = "password_reset"


def _password_reset_expire_minutes() -> int:
    try:
        return int(getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))
    except (TypeError, ValueError):
        return 30

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        # Check email if username not found, sometimes form_data.username actually contains an email
        user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data={"id" : str(user.id), "username": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
        if username is None:
            raise credentials_exception
        _id = payload.get("id")
        if _id is None:
            raise credentials_exception
        token_data = TokenData(id=_id, username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == UUID(token_data.id)).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/forgot-password", tags=["Authentication"])
async def forgot_password(data: ForgotPasswordModel, db: Session = Depends(get_db)):
    """Start a password reset.

    Always responds with the same generic message so the endpoint cannot be
    used to discover which emails are registered. When the email matches a
    user, a short-lived reset link is emailed to them.
    """
    generic_response = {
        "message": "If an account with that email exists, a password reset link has been sent."
    }

    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        return generic_response

    token = create_purposed_token(
        subject=str(user.id),
        purpose=PASSWORD_RESET_PURPOSE,
        expires_minutes=_password_reset_expire_minutes(),
    )

    reset_base = getenv("FRONTEND_RESET_URL", "http://localhost:5173/reset-password")
    separator = "&" if "?" in reset_base else "?"
    reset_link = f"{reset_base}{separator}token={token}"

    send_email(
        to=user.email,
        subject="Reset your SmartHome password",
        html=(
            f"<p>Hi {user.username},</p>"
            f"<p>We received a request to reset your password. "
            f"Click the link below to choose a new one. This link expires soon.</p>"
            f"<p><a href=\"{reset_link}\">Reset your password</a></p>"
            f"<p>If you didn't request this, you can safely ignore this email.</p>"
        ),
    )

    return generic_response


@router.post("/reset-password", tags=["Authentication"])
async def reset_password(data: ResetPasswordModel, db: Session = Depends(get_db)):
    """Complete a password reset using the token emailed to the user."""
    try:
        user_id = verify_purposed_token(data.token, PASSWORD_RESET_PURPOSE)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if not validate_password(data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be between 8 and 72 characters, contain an uppercase letter, a lowercase letter, a number and a symbol.",
        )

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password = get_password_hash(data.new_password)
    db.commit()

    return {"message": "Password has been reset successfully."}