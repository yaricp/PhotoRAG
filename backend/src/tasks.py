from src.queue import task_queue
from src.graphs.ingestion import ingest_workflow

@task_queue.task()
def process_photo_task(filepath: str):
    # This runs in the background Huey process
    # It triggers the LangGraph ingestion pipeline
    result = ingest_workflow.invoke({"filepath": filepath})
    return result
