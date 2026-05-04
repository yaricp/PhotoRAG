import os
from huey import SqliteHuey


translate_queue = SqliteHuey(
    "translate",
    filename=os.path.join(os.getcwd(), "../translate.sqlite3")
)


@translate_queue.on_startup()
def warm_translator():
    from src.ai.registry import registry
    import src.tasks.translation_tasks
    _ = registry.translator