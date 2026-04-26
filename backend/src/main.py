from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Photo Describer MVP")

class WatchRequest(BaseModel):
    path: str

@app.post("/api/watch")
def trigger_directory_watch(request: WatchRequest):
    # Triggers Tier 1 watchdog
    return {"status": "watching", "target": request.path}

@app.get("/api/stream")
def sse_event_stream():
    # Will yield Async generator for SSE UI updates
    return {"status": "stream_placeholder"}
