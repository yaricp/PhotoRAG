from loguru import logger

from src.ai.registry import registry
from src.db_service import get_translatable_content_and_meta
from src.tasks import _finish_task
from src.queues.translation_queue import translation_queue
from src.models.translation import TranslateRequest


@translation_queue.task()
def translate_text_task(translate_request: TranslateRequest):
    """Translates text"""
    return registry.translator.translate(translate_request)
