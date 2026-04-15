from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args = {"check_same_thread": False}
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()