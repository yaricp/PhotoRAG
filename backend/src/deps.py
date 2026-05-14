from src.db.database import SessionLocal
from src.db.database import Session


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
