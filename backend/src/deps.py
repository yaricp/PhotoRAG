from src.database import SessionLocal
from src.database import Session
from src.ai.registry import registry
from src.ai.translator import Translator


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_translator() -> Translator:
    return registry.translator
