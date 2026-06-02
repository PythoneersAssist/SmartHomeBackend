from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from os import getenv
from jose import JWTError

SECRET_KEY = getenv("SECRET_KEY")
ALGORITHM = getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = getenv("ACCESS_TOKEN_EXPIRE_MINUTES")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_purposed_token(subject: str, purpose: str, expires_minutes: int) -> str:
    """Create a short-lived JWT scoped to a single purpose.

    Used for one-off actions such as password resets and account deletion. The
    `purpose` claim is checked on verification so a token minted for one action
    cannot be replayed against another.
    """
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {"sub": str(subject), "purpose": purpose, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_purposed_token(token: str, purpose: str) -> str:
    """Verify a purpose-scoped token and return its subject.

    Raises `JWTError` if the token is invalid, expired, or was issued for a
    different purpose.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("purpose") != purpose:
        raise JWTError("Token purpose mismatch")
    subject = payload.get("sub")
    if not subject:
        raise JWTError("Token subject missing")
    return subject


def verify_token(token: str) -> dict:
    """Decode and verify a JWT access token.

    Returns the token payload as a dict. Normalizes common fields so callers
    can look up the user id under the `sub` key (falls back to `id`).
    Raises `JWTError` when token is invalid.
    """
    if not token:
        raise JWTError("Token is missing")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise

    # Normalize: prefer 'sub' (subject); if backend issued token with 'id', map it
    if "sub" not in payload and "id" in payload:
        payload["sub"] = payload["id"]

    return payload
