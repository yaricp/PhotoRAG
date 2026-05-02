from src.install import run_install, init_db
from src.database import SessionLocal

db = SessionLocal()
init_db(db)
run_install(db)

print("Full install completed.")