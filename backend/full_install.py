from src.db.database import SessionLocal
from src.install import run_install

db = SessionLocal()
run_install(db)

print("Full install completed.")
