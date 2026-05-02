import os
from huey import SqliteHuey


embedding_queue = SqliteHuey(
    "embedding",
    filename=os.path.join(os.getcwd(), "../embedding.sqlite3")
)


@embedding_queue.on_startup()
def warm_embedding():
    from src.ai.registry import registry
    from src.tasks import embedding_tasks
    _ = registry.nomic_embedder
