"""
Initialise the database schema and seed foundational data.
Called by the setup wizard's init-db step. Model downloads
happen separately in the wizard's download step.
"""
from src.install import init_db, install_categories
from src.db.database import SessionLocal

db = SessionLocal()
try:
    init_db(db)
    install_categories(db)  # seed default categories so clip can compute embeddings
    db.commit()
finally:
    db.close()

print("Database initialised.")
