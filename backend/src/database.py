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
SessionLocal: Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Engine, "connect")
def load_sqlite_extensions(dbapi_connection, connection_record):
    try:
        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)
        logger.info("✅ sqlite-vec loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load sqlite-vec: {e}")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
