import os
import sys
import time
import subprocess
from loguru import logger
from sqlalchemy import text

from src.database import engine, SessionLocal
from src.models import Base, ModelState
from src.tasks import download_models_task

from src.config import Api_Settings


def init_db():
    logger.info("Initializing Database...")

    # 1. Create tables
    Base.metadata.create_all(bind=engine)

    # 2. Create VSS tables
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS photo_embeddings_vss
            USING vec0(embedding FLOAT[768]);
        """))
    
    # 3. Initialize model states if empty
    db = SessionLocal()
    for model_name in ["clip", "vision", "embedding", "categories"]:
        state = db.query(ModelState).filter_by(name=model_name).first()
        if not state:
            db.add(ModelState(name=model_name, status="pending"))
    db.commit()
    db.close()


def start_workers():
    logger.info("Starting Background Workers...")
    # Spawn Huey consumer
    return subprocess.Popen([
        sys.executable, "-m", "huey.bin.huey_consumer", 
        "src.tasks.task_queue", "-w", "4", "-k", "thread"
    ])


def check_and_bootstrap():
    logger.info("Checking AI Models readiness...")
    db = SessionLocal()
    states = db.query(ModelState).all()
    
    needs_download = any(s.status != "ready" for s in states)
    if needs_download:
        logger.info("Models not ready. Triggering background download...")
        download_models_task() # Trigger the async task
    else:
        logger.info("All models ready.")
    db.close()


def start_api():
    logger.info("Starting FastAPI Server...")
    # Use uvicorn to run our app
    try:
        import uvicorn
        uvicorn.run(
            "src.main:app",
            host=Api_Settings().API_HOST,
            port=Api_Settings().API_PORT,
            reload=True
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    init_db()
    
    # 1. Start Workers first (so they can handle the bootstrap task)
    worker_proc = start_workers()
    
    # 2. Check logic and bootstrap if needed
    time.sleep(2) # Give workers a moment to breathe
    check_and_bootstrap()
    
    # 3. Start API (Blocking call)
    try:
        start_api()
    finally:
        logger.info("Stopping workers...")
        worker_proc.terminate()
