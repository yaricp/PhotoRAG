import os
from huey import SqliteHuey


translation_queue = SqliteHuey(
    "translation",
    filename=os.path.join(os.getcwd(), "../translation.sqlite3")
)


@translation_queue.on_startup()
def warm_translator():
    from src.ai.registry import registry
    import src.tasks.translation_tasks
    _ = registry.translator