"""
Migration: add model_provider column to ai_model_configs table

Allows specifying the LangChain provider explicitly (e.g. "google_genai",
"openai", "anthropic") so init_chat_model() does not auto-detect the wrong one.

Run once against an existing database:
    cd backend && python -m src.migrate_model_provider
"""
from loguru import logger
from src.db.database import engine
import sqlalchemy


def run():
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(
            sqlalchemy.text("PRAGMA table_info(ai_model_configs)")
        )]
        if "model_provider" in cols:
            logger.info("Already migrated — model_provider column exists on ai_model_configs.")
            return

        logger.info("Adding model_provider column to ai_model_configs")
        conn.execute(sqlalchemy.text(
            "ALTER TABLE ai_model_configs ADD COLUMN model_provider VARCHAR"
        ))
        conn.commit()
        logger.info("Migration complete.")


if __name__ == "__main__":
    run()
