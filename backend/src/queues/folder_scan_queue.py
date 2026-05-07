import os
from huey import SqliteHuey


folder_scan_queue = SqliteHuey(
    "folder_scan",
    filename=os.path.join(os.getcwd(), "../folder_scan.sqlite3")
)


@folder_scan_queue.on_startup()
def warm_folder_scan_queue():
    """Warms up the folder scan queue"""
    import src.tasks.folder_scanners
    from src.tasks.folder_scanners import start_existing_folder_scanners

    start_existing_folder_scanners()

