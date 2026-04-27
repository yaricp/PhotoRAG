from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import Settings


settings = Settings()
if settings.DATABASE_DIALECT == "sqlite":
    DATABASE_URL: str = f"sqlite:///{settings.DATABASE_NAME}"
else:
    DATABASE_URL: str = f"{settings.DATABASE_DIALECT}+{settings.DATABASE_DRIVER}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
