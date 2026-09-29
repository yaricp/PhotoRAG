import sqlite_vec
from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.config import Database_Settings

settings = Database_Settings()
DATABASE_URL: str = f"sqlite:///{settings.DATABASE_NAME}"

engine = create_engine(DATABASE_URL, connect_args={"timeout": 30}, poolclass=NullPool)
SessionLocal: sessionmaker[Session] = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def load_sqlite_extensions(dbapi_connection, connection_record):
    try:
        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)
        logger.info("✅ sqlite-vec loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load sqlite-vec: {e}")
    try:
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA busy_timeout=30000")
    except Exception as e:
        logger.error(f"Failed to set SQLite pragmas: {e}")


def migrate_pipeline_runs(bind=engine) -> None:
    """Add run/attempt tracking without replacing legacy rows or photo content.

    The SQLite online backup includes WAL data and is retained for rollback.
    BEGIN IMMEDIATE serializes concurrent startup migrations.
    """
    import sqlite3
    from pathlib import Path

    from sqlalchemy import inspect, text

    from src.models import PipelineRun

    inspector = inspect(bind)
    if "pipeline_tasks" not in inspector.get_table_names():
        PipelineRun.__table__.create(bind, checkfirst=True)
        return
    columns = {column["name"] for column in inspector.get_columns("pipeline_tasks")}
    if "run_id" in columns:
        return
    database = bind.url.database
    if database and database != ":memory:":
        backup = Path(str(database) + ".pre-pipeline-runs.bak")
        if not backup.exists():
            with sqlite3.connect(database) as source, sqlite3.connect(str(backup)) as target:
                source.backup(target)
    with bind.connect() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pipeline_tasks)")}
            if "run_id" in columns:
                conn.commit()
                return
            PipelineRun.__table__.create(conn, checkfirst=True)
            conn.exec_driver_sql("ALTER TABLE pipeline_tasks ADD COLUMN run_id INTEGER REFERENCES pipeline_runs(id)")
            conn.exec_driver_sql("ALTER TABLE pipeline_tasks ADD COLUMN attempt INTEGER NOT NULL DEFAULT 1")
            conn.exec_driver_sql("ALTER TABLE pipeline_tasks ADD COLUMN skip_reason TEXT")
            conn.exec_driver_sql("ALTER TABLE pipeline_tasks ADD COLUMN required BOOLEAN NOT NULL DEFAULT 1")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pipeline_tasks_run_id ON pipeline_tasks(run_id)")
            photo_ids = conn.execute(text("SELECT id FROM photos")).scalars().all()
            for photo_id in photo_ids:
                statuses = (
                    conn.execute(text("SELECT status FROM pipeline_tasks WHERE photo_id=:id"), {"id": photo_id})
                    .scalars()
                    .all()
                )
                status = (
                    "interrupted"
                    if any(s in ("pending", "running") for s in statuses)
                    else ("completed-with-errors" if any(s == "failed" for s in statuses) else "completed")
                )
                result = conn.execute(
                    text(
                        "INSERT INTO pipeline_runs (photo_id, source, status, created_at) VALUES (:id, 'legacy', :status, CURRENT_TIMESTAMP)"
                    ),
                    {"id": photo_id, "status": status},
                )
                conn.execute(
                    text("UPDATE pipeline_tasks SET run_id=:run WHERE photo_id=:id"),
                    {"id": photo_id, "run": result.lastrowid},
                )
            conn.execute(text("UPDATE pipeline_tasks SET status='interrupted' WHERE status IN ('pending', 'running')"))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
