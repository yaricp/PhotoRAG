import os
from huey import SqliteHuey


vision_queue = SqliteHuey(
    "vision",
    filename=os.path.join(os.getcwd(), "../vision.sqlite3")
)


@vision_queue.on_startup()
def warm_vision():
    from src.ai.registry import registry
    import src.tasks.vision_tasks
    _ = registry.vision_generator