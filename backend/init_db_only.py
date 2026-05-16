"""
Initialise the database schema only — no model downloads.
Called by the setup wizard's init-db step. Model downloads
happen separately in the wizard's download step.
"""
from src.install import init_db
from src.db.database import SessionLocal

db = SessionLocal()
try:
    init_db(db)
    db.commit()
finally:
    db.close()

print("Database initialised.")
