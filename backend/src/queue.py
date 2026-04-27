from huey import SqliteHuey

# A lightweight SQLite-backed queue for safely dispatching heavy ML inferences
task_queue = SqliteHuey(
    name='photo_processor_queue',
    filename='../tasks.sqlite3'
)
