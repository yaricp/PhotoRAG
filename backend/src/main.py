from fastapi import FastAPI
from pydantic import BaseModel

from src.observer import start_observer

app = FastAPI(title="Photo Describer MVP")

class WatchRequest(BaseModel):
    path: str

# Store active observers in a global dict to manage their lifecycle
active_observers = {}

from src.db_service import get_all_model_states
from src.database import SessionLocal

@app.get("/api/system/status")
def get_system_status():
    db = SessionLocal()
    try:
        states = get_all_model_states(db)
        return {
            "ready": all(s.status == "ready" for s in states),
            "models": [{"name": s.name, "status": s.status} for s in states]
        }
    finally:
        db.close()

@app.post("/api/watch")
def trigger_directory_watch(request: WatchRequest):
    if request.path not in active_observers:
        try:
            observer = start_observer(request.path)
            active_observers[request.path] = observer
            return {"status": "watching", "target": request.path}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "already_watching", "target": request.path}

@app.get("/api/stream")
def sse_event_stream():
    # Will yield Async generator for SSE UI updates
    return {"status": "stream_placeholder"}
