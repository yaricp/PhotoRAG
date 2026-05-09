"""
Migration: move geoposition FK from Geoposition.photo_id → Photo.geoposition_id

Run once against an existing database:
    cd backend && python -m src.migrate_geoposition
"""
from loguru import logger
from src.database import engine


def run():
    with engine.connect() as conn:
        # Check if already migrated
        cols = [row[1] for row in conn.execute(
            __import__('sqlalchemy').text("PRAGMA table_info(photos)")
        )]
        if 'geoposition_id' in cols:
            logger.info("Already migrated — geoposition_id column exists on photos.")
            return

        logger.info("Step 1: add geoposition_id to photos")
        conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE photos ADD COLUMN geoposition_id INTEGER REFERENCES geopositions(id)"
        ))

        logger.info("Step 2: populate photos.geoposition_id from existing geopositions")
        conn.execute(__import__('sqlalchemy').text(
            "UPDATE photos SET geoposition_id = "
            "(SELECT id FROM geopositions WHERE geopositions.photo_id = photos.id)"
        ))

        logger.info("Step 3: drop photo_id column from geopositions (requires SQLite >= 3.35)")
        conn.execute(__import__('sqlalchemy').text(
            "ALTER TABLE geopositions DROP COLUMN photo_id"
        ))

        conn.commit()
        logger.info("Migration complete.")


if __name__ == "__main__":
    run()
