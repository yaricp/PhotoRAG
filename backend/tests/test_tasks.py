from src.tasks import process_photo_task
from src.queue import task_queue

from huey.api import TaskWrapper

def test_task_is_registered():
    assert isinstance(process_photo_task, TaskWrapper)
