import os
import sys

# Set environment variables BEFORE any app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.database import Base, get_db
from main import app
from utils.security import get_password_hash

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///./test_database.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    

@pytest.fixture()
def db_session():
    """Provide a transactional database session for tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with overridden DB dependency."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

TEST_USER = {
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "StrongPass1!"
}

TEST_USER_2 = {
    "username": "testuser2",
    "email": "testuser2@example.com",
    "password": "AnotherPass2@"
}


def create_test_user(client: TestClient, user_data: dict = None) -> dict:
    """Register a user via the API and return the user data used."""
    data = user_data or TEST_USER.copy()
    response = client.post("/user/create", json=data)
    return {"response": response, "user": data}


def get_auth_token(client: TestClient, username: str = None, password: str = None) -> str:
    """Obtain a bearer token for a registered user."""
    _username = username or TEST_USER["username"]
    _password = password or TEST_USER["password"]
    response = client.post(
        "/token",
        data={"username": _username, "password": _password},
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict:
    """Return Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


def create_user_and_login(client: TestClient, user_data: dict = None) -> tuple[dict, str]:
    """Helper: create a user and return (user_data, token)."""
    data = user_data or TEST_USER.copy()
    create_test_user(client, data)
    token = get_auth_token(client, data["username"], data["password"])
    return data, token
