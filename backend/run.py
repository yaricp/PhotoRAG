# run.py
import signal
import subprocess
import sys
from pathlib import Path

from loguru import logger

from src.config import (
    Api_Settings,
    CLIP_Settings,
    Embedding_Settings,
    OCR_Settings,
    Translation_Settings,
    Vision_Settings,
)
from src.data_dir import migrate_legacy_data, resolve_app_data_dir

QUEUE_MODULE = {
    "clip": "src.queues.clip_queue.clip_queue",
    "vision": "src.queues.vision_queue.vision_queue",
    "embedding": "src.queues.embedding_queue.embedding_queue",
    "translate": "src.queues.translation_queue.translation_queue",
    "ocr": "src.queues.ocr_queue.ocr_queue",
    "folder_scan": "src.queues.folder_scan_queue.folder_scan_queue",
}

_STOP_TIMEOUT = 60  # seconds to wait for graceful shutdown before SIGKILL
# Huey workers finish their current task before stopping on SIGTERM.
# Vision/CLIP inference can take 30s on CPU, so 60s is a safe budget.


def start_workers() -> list[subprocess.Popen]:
    """Starts worker processes for local models."""
    vision_settings = Vision_Settings()
    clip_settings = CLIP_Settings()
    embedding_settings = Embedding_Settings()
    translation_settings = Translation_Settings()
    ocr_settings = OCR_Settings()

    list_queues = []
    if vision_settings.VISION_MODE == "local":
        list_queues.append("vision")
    if clip_settings.CLIP_MODE == "local":
        list_queues.append("clip")
    if embedding_settings.EMBEDDING_MODE == "local":
        list_queues.append("embedding")
    if translation_settings.TRANSLATOR_MODE == "local":
        list_queues.append("translate")
    if ocr_settings.OCR_MODE == "local":
        list_queues.append("ocr")
    list_queues.append("folder_scan")

    logger.info(f"[workers] Starting workers for: {list_queues}")
    procs = []
    for model in list_queues:
        queue_module = QUEUE_MODULE.get(model)
        if queue_module is None:
            logger.error(f"[workers] Unknown model: {model}")
            continue
        logger.info(f"[workers] Starting worker for: {model} → {queue_module}")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "huey.bin.huey_consumer",
                queue_module,
                "-w",
                "1",
                "-k",
                "thread",
            ]
        )
        procs.append(proc)
    return procs


def stop_workers(procs: list[subprocess.Popen]) -> None:
    """Gracefully stop all worker processes; force-kill any that linger."""
    if not procs:
        return
    logger.info(f"[shutdown] Sending SIGTERM to {len(procs)} worker(s)...")
    for proc in procs:
        try:
            proc.terminate()
        except OSError:
            pass  # already dead

    # Wait for graceful exit
    for proc in procs:
        try:
            proc.wait(timeout=_STOP_TIMEOUT)
            logger.info(f"[shutdown] Worker PID {proc.pid} stopped.")
        except subprocess.TimeoutExpired:
            logger.warning(f"[shutdown] Worker PID {proc.pid} did not stop in {_STOP_TIMEOUT}s — sending SIGKILL.")
            try:
                proc.kill()
                proc.wait()
            except OSError:
                pass

    logger.info("[shutdown] All workers stopped.")


def start_api():
    import uvicorn

    cfg = Api_Settings()
    logger.info(f"[api] Starting FastAPI on {cfg.API_HOST}:{cfg.API_PORT}")
    uvicorn.run(
        "src.main:app",
        host=cfg.API_HOST,
        port=cfg.API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    _project_root = Path(__file__).parent.parent
    _app_data_dir = resolve_app_data_dir()
    migrate_legacy_data(_project_root, _app_data_dir)
    logger.info(f"[startup] APP_DATA_DIR = {_app_data_dir}")

    worker_procs = start_workers()

    # Ensure workers are cleaned up on SIGTERM (e.g. from Docker / systemd)
    def _sigterm_handler(signum, frame):
        stop_workers(worker_procs)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sigterm_handler)

    try:
        start_api()
    except KeyboardInterrupt:
        logger.info("[shutdown] Ctrl+C received.")
    finally:
        stop_workers(worker_procs)
