# run.py
import sys
import subprocess
from loguru import logger

from src.config import Api_Settings, ML_Settings


QUEUE_MODULE = {
    "clip":      "src.queues.clip_queue.clip_queue",
    "vision":    "src.queues.vision_queue.vision_queue",
    "embedding": "src.queues.embedding_queue.embedding_queue",
}

def start_workers(local_models: list[str]) -> list[subprocess.Popen]:
    procs = []
    for model in local_models:
        queue_module = QUEUE_MODULE[model]
        logger.info(f"[workers] Starting worker for: {model} → {queue_module}")
        proc = subprocess.Popen([
            sys.executable, "-m", "huey.bin.huey_consumer",
            queue_module,
            "-w", "1",
            "-k", "thread",
        ])
        procs.append(proc)
    return procs


def start_api():
    import uvicorn
    cfg = Api_Settings()
    logger.info(f"[api] Starting FastAPI on {cfg.API_HOST}:{cfg.API_PORT}")
    uvicorn.run(
        "src.main:app",
        host=cfg.API_HOST,
        port=cfg.API_PORT,
        reload=False,  # False в продакшне
    )


if __name__ == "__main__":
    # 1. Воркеры только для local моделей
    ml = ML_Settings()
    worker_procs = start_workers(ml.local_models)

    # 2. API (блокирующий вызов)
    try:
        start_api()
    finally:
        logger.info("[shutdown] Stopping worker processes...")
        for proc in worker_procs:
            proc.terminate()