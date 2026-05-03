from src.install import run_install
from src.database import SessionLocal

db = SessionLocal()
run_install(db)

print("Full install completed.")