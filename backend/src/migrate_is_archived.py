"""
Migration: add is_archived column to photos table

Run once against an existing database:
    cd backend && python -m src.migrate_is_archived
"""
from loguru import logger
from src.db.database import engine
import sqlalchemy


def run():
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(
            sqlalchemy.text("PRAGMA table_info(photos)")
        )]
        if 'is_archived' in cols:
            logger.info("Already migrated — is_archived column exists on photos.")
            return

        logger.info("Adding is_archived column to photos")
        conn.execute(sqlalchemy.text(
            "ALTER TABLE photos ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"
        ))
        conn.commit()
        logger.info("Migration complete.")


if __name__ == "__main__":
    run()
