import sqlite_vec
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from src.config import Database_Settings


settings = Database_Settings()
if settings.DATABASE_DIALECT == "sqlite":
    DATABASE_URL: str = f"sqlite:///{settings.DATABASE_NAME}"
else:
    DATABASE_URL: str = f"{settings.DATABASE_DIALECT}+{settings.DATABASE_DRIVER}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal: sessionmaker[Session] = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Engine, "connect")
def load_sqlite_extensions(dbapi_connection, connection_record):
    try:
        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)
        logger.info("✅ sqlite-vec loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load sqlite-vec: {e}")


@event.listens_for(Engine, "close")
def checkpoint_on_close(dbapi_connection, connection_record):
    """Flush WAL back into the main DB file whenever a connection is returned to the pool."""
    try:
        dbapi_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass

