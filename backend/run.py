import subprocess
import sys
import time
import os
from src.database import engine, SessionLocal
from src.models import Base, ModelState
from src.tasks import download_models_task

def init_db():
    print("Initializing Database...")
    Base.metadata.create_all(bind=engine)
    
    # Initialize model states if empty
    db = SessionLocal()
    for model_name in ["clip", "vision", "embedding"]:
        state = db.query(ModelState).filter_by(name=model_name).first()
        if not state:
            db.add(ModelState(name=model_name, status="pending"))
    db.commit()
    db.close()

def start_workers():
    print("Starting Background Workers...")
    # Spawn Huey consumer
    return subprocess.Popen([
        sys.executable, "-m", "huey.bin.huey_consumer", 
        "src.tasks.task_queue", "-w", "4", "-k", "thread"
    ])

def check_and_bootstrap():
    print("Checking AI Models readiness...")
    db = SessionLocal()
    states = db.query(ModelState).all()
    
    needs_download = any(s.status != "ready" for s in states)
    if needs_download:
        print("Models not ready. Triggering background download...")
        download_models_task() # Trigger the async task
    else:
        print("All models ready.")
    db.close()

def start_api():
    print("Starting FastAPI Server...")
    # Use uvicorn to run our app
    try:
        import uvicorn
        uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
    except KeyboardInterrupt:
        print("Shutting down...")

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
        print("Stopping workers...")
        worker_proc.terminate()
