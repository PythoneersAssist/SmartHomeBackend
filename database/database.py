import logging
from os import getenv

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger("uvicorn.error")

# DATABASE_URL is provided by the hosting platform (e.g. Azure App Settings).
# Falls back to a local SQLite file for development.
SQLALCHEMY_DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./database.db")

# Normalise legacy / driver-less Postgres URLs to the psycopg (v3) driver.
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    pool_pre_ping=not is_sqlite,
)

# Diagnostic: log the connection target SQLAlchemy actually parsed (never the
# password). If the host/username here doesn't match your real DB, the
# DATABASE_URL is mis-parsed (usually unencoded special chars in credentials).
logger.warning(
    "DB connection target -> dialect=%s host=%r port=%r user=%r database=%r",
    engine.url.get_backend_name(),
    engine.url.host,
    engine.url.port,
    engine.url.username,
    engine.url.database,
)

SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)

Base = declarative_base()


def ensure_schema_upgrades() -> None:
    """Apply lightweight in-place upgrades for legacy SQLite databases."""
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        room_columns = conn.execute(text("PRAGMA table_info(rooms)")).fetchall()
        column_names = {row[1] for row in room_columns}

        if room_columns and "room_type" not in column_names:
            conn.execute(text("ALTER TABLE rooms ADD COLUMN room_type VARCHAR(64) DEFAULT 'OTHER'"))
            conn.execute(text("UPDATE rooms SET room_type = 'OTHER' WHERE room_type IS NULL OR room_type = ''"))

        automation_columns = conn.execute(text("PRAGMA table_info(automations)")).fetchall()
        automation_column_names = {row[1] for row in automation_columns}

        if automation_columns and "turn_on" not in automation_column_names:
            conn.execute(text("ALTER TABLE automations ADD COLUMN turn_on BOOLEAN DEFAULT 1"))
            conn.execute(text("UPDATE automations SET turn_on = 1 WHERE turn_on IS NULL"))

        if automation_columns and "parameters" not in automation_column_names:
            conn.execute(text("ALTER TABLE automations ADD COLUMN parameters JSON"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()