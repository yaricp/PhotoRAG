"""
Initialise the database schema and seed foundational data.
Called by the setup wizard's init-db step. Model downloads
happen separately in the wizard's download step.
"""

from src.db.database import SessionLocal
from src.install import init_db, seed_template_vocabularies

db = SessionLocal()
try:
    init_db(db)
    seed_template_vocabularies(db)  # seed categories/tags and remote CLIP candidate names
    db.commit()
finally:
    db.close()

print("Database initialised.")
