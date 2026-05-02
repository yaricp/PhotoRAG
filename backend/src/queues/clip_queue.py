import os
from huey import SqliteHuey


clip_queue = SqliteHuey(
    "clip",
    filename=os.path.join(os.getcwd(), "../clip.sqlite3")
)


@clip_queue.on_startup()
def warm_clip():
    from src.ai.registry import registry
    from src.tasks import clip_tasks
    _ = registry.clip_tagger
