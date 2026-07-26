import sqlite_vec
from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.config import Database_Settings

settings = Database_Settings()
DATABASE_URL: str = f"sqlite:///{settings.DATABASE_NAME}"

engine = create_engine(DATABASE_URL, connect_args={"timeout": 30}, poolclass=NullPool)
SessionLocal: sessionmaker[Session] = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def load_sqlite_extensions(dbapi_connection, connection_record):
    try:
        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)
        logger.info("✅ sqlite-vec loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load sqlite-vec: {e}")
    try:
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA busy_timeout=30000")
    except Exception as e:
        logger.error(f"Failed to set SQLite pragmas: {e}")
