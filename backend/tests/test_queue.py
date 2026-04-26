import os
from src.queue import task_queue

def test_huey_is_configured_with_sqlite():
    assert task_queue.name == 'photo_processor_queue'
