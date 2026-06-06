"""
Re-translation pipeline.

Triggered when the user changes the UI language. Translates every photo's
description to the new language and shows progress on the Processing Page
via the standard PipelineTask / pipeline_tracker mechanism.
"""

import asyncio

from loguru import logger
from sqlalchemy import text

from src.db.database import SessionLocal
from src.pipeline_tracker import init_pipeline_tasks
from src.tasks.translation_tasks import translate_description_task_for_retranslation

_RETRANSLATION_TASKS = ["translate_description_task"]
_MAX_CONCURRENT = 4


async def start_retranslation(new_lang: str) -> None:
    """
    Re-translate all photo descriptions to new_lang.

    When new_lang is "en", descriptions are already in English — nothing to do.
    Each photo gets a PipelineTask row (phase="retranslation") so progress is
    visible on the Processing Page alongside other pipeline work.
    """
    if new_lang == "en":
        logger.info("[retranslation] language is 'en', nothing to translate")
        return

    with SessionLocal() as db:
        photo_ids = (
            db.execute(text("SELECT id FROM photos WHERE description IS NOT NULL AND description != ''"))
            .scalars()
            .all()
        )

    if not photo_ids:
        logger.info("[retranslation] no photos with descriptions, skipping")
        return

    logger.info(f"[retranslation] queuing {len(photo_ids)} photos → '{new_lang}'")
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _translate_one(photo_id: int) -> None:
        async with semaphore:
            init_pipeline_tasks(photo_id, "retranslation", _RETRANSLATION_TASKS)
            try:
                await translate_description_task_for_retranslation(photo_id, new_lang)
            except Exception as exc:
                logger.error(f"[retranslation] photo_id={photo_id} failed: {exc}")

    await asyncio.gather(*[_translate_one(pid) for pid in photo_ids])
    logger.info(f"[retranslation] finished {len(photo_ids)} photos")
