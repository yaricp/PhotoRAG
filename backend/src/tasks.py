import os
from loguru import logger

from src.queue import task_queue
from src.metadata import get_exif_data
from src.ai.ocr import extract_text_from_image
from src.ai.registry import registry
from src.config import ML_Settings
from src.database import SessionLocal
from src.db_service import (
    get_photo_by_id,
    get_or_create_photo,
    update_model_status,
    get_model_status,
    get_or_create_camera,
    update_photo_geoposition,
    get_or_create_keyword,
    add_photo_tag_with_score,
    get_all_categories,
    get_or_create_category,
    add_photo_category_with_score,
    get_or_create_job,
    update_job_tasks,
    delete_job,
)
from src.vector_db_services import store_photo_embedding
from src.models import (
    Photo, PhotoTag, PhotoCategory, Geoposition, ProcessingJob
)
from src.utils import (
    load_categories_from_json, extract_exif,
    convert_ocr_result_to_json, parse_datetime
)
from src.geo import GeoEnricher


def phase_logic(phase:str) ->tuple[str, str]:
    new_tasks = ""
    next_phase_name = ""
    if phase == "init":
        next_phase_name = "first"
        new_tasks = "metadata_task,auto_tag_clip_task,categorize_photo_task,vision_task,"
    elif phase == "first":
        next_phase_name = "second"
        new_tasks = "final_embedding_task,"
    elif phase == "second":
        next_phase_name = "third"
        new_tasks = "ocr_task,"
    return next_phase_name, new_tasks


def start_pipeline(photo_id: int):
    """
    Starts the pipeline for the given photo.
    """
    logger.info(f"Starting pipeline for photo {photo_id}")
    db=SessionLocal()
    try:
        next_phase_name, new_tasks = phase_logic("init")
        get_or_create_job(
            db,
            photo_id=photo_id,
            phase=next_phase_name,
            tasks=new_tasks
        )
        logger.info(f"Job created for photo {photo_id}")
        start_next_phase_tasks(
            photo_id=photo_id,
            phase=next_phase_name,
            tasks=new_tasks
        )
        logger.info(f"Tasks dispatched for photo {photo_id}")
    except Exception as e:
        logger.error(f"Error in start_pipeline for photo {photo_id}: {e}")
        delete_job(db, photo_id, next_phase_name)
    finally:
        db.close()


def start_next_phase_tasks(photo_id: int, phase: str, tasks: str):
    for task_name in tasks.split(","):
        if task_name == "final_embedding_task":
            final_embedding_task(photo_id, phase=phase)
            logger.info(f"Final embedding task dispatched for photo {photo_id}")
        elif task_name == "metadata_task":
            metadata_task(photo_id, phase=phase)
            logger.info(f"Metadata task dispatched for photo {photo_id}")
        elif task_name == "auto_tag_clip_task":
            auto_tag_clip_task(photo_id, phase=phase)
            logger.info(f"Auto tag clip task dispatched for photo {photo_id}")
        elif task_name == "categorize_photo_task":
            categorize_photo_task(photo_id, phase=phase)
            logger.info(f"Categorize photo task dispatched for photo {photo_id}")
        elif task_name == "vision_task":
            vision_task(photo_id, phase=phase)
            logger.info(f"Vision task dispatched for photo {photo_id}")
        elif task_name == "ocr_task":
            ocr_task(photo_id, phase=phase)
            logger.info(f"OCR task dispatched for photo {photo_id}")
        elif task_name == "is_this_document_task":
            is_this_document_task(photo_id, phase=phase)
            logger.info(f"Is this document task dispatched for photo {photo_id}")
    

def finish_task(photo_id: int, phase: str, name: str):
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter_by(photo_id=photo_id, phase=phase).first()
        if not job:
            return
        job.tasks = job.tasks.replace(name+",", "")
        db.commit()
        logger.info(f"Task {name} finished for photo {photo_id}")
        logger.info(f"Remaining tasks: {job.tasks}")
        if job.tasks == "":
            next_phase_name, new_tasks = phase_logic(job.phase)
            logger.info(f"Next phase: {next_phase_name}")
            logger.info(f"New tasks: {new_tasks}")
            if new_tasks != "":   
                update_job_tasks(
                    db, 
                    photo_id=photo_id,
                    phase=phase,
                    new_phase=next_phase_name,
                    tasks=new_tasks
                )
                start_next_phase_tasks(
                    photo_id=photo_id,
                    phase=next_phase_name,
                    tasks=new_tasks
                )
            else:
                delete_job(db, photo_id, phase)
                logger.info(f"Job {job.id} deleted for photo {photo_id}")
    except Exception as e:
        logger.error(f"Error finishing task {name} phase {phase} for photo {photo_id}: {e}")
        
    finally:
        db.close()


@task_queue.task()
def final_embedding_task(photo_id: int, phase: str):
    """Aggregates results and saves 768-dim vector using Warm Registry Embedder."""
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if not photo:
            return

        # 1. Gather components
        tags = [pt.tag.name for pt in photo.tags_rel]
        categories = [pc.category.name for pc in photo.categories_rel]
        main_category = categories[0] if categories else "Uncategorized"
        
        geo = db.query(Geoposition).filter_by(photo_id=photo_id).first()
        location = geo.address if geo and geo.address else "Unknown Location"
        logger.info(f"Embedding photo with: {photo.description}")
        logger.info(f"Embedding photo tags: {tags}")
        logger.info(f"Embedding photo categories: {categories}")
        logger.info(f"Embedding photo geoposition: {location}")
        # 2. Format Synthesis Template
        photo_text = f"""
Scene: {photo.description}
Tags: {", ".join(tags)}
Category: {main_category}
Location: {location}
"""
        logger.info(f"Embedding photo text: {photo_text}")
        # 3. Generate Embedding (Using Warm Registry)
        model = registry.nomic_embedder
        embedding = registry.embedder_encode_text(
            text=photo_text, purpose="save"
        )
        # 4. Persist to pgvector column
        store_photo_embedding(db, photo.id, embedding, model.name)
        logger.info(f"Embedding photo embedding saved")
        db.commit()
        logger.info(f"Embedding photo embedding committed")
        finish_task(
            photo_id=photo_id, phase=phase, name="final_embedding_task"
        )
    except Exception as e:
        logger.error(f"Error in task for photo {photo_id}: {e}")
        delete_job(db, photo_id, phase)
    finally:
        db.close()


@task_queue.task()
def download_models_task():
    """First-install bootstrap: downloads all models to disk if not already present.

    Responsibility: DISK / NETWORK only.
    - Checks ModelState table before acting (idempotent).
    - Calls model.download() directly — never goes through AIModelRegistry.
    The Registry is a separate RAM-only concern.
    """
    db = SessionLocal()

    # 1. Seed default categories (idempotent — get_or_create is safe to repeat)
    if get_model_status(db, "categories") == "ready":
        logger.info("Categories: already ready, skipping seeding.")
    else:
        logger.info("Categories: seeding default categories...")
        base_dir = os.path.dirname(os.path.dirname(__file__))
        defaults_path = os.path.join(base_dir, "defaults", "default_categories.json")
        defaults = load_categories_from_json(defaults_path)
        for cat in defaults:
            get_or_create_category(db, cat['name'], cat['prompt'])
        update_model_status(db, "categories", "ready")
        logger.info("Categories: seeding complete.")

    # 2. CLIP weights + Open Images vocabulary
    from src.ai.clip import ClipTagger
    if get_model_status(db, "clip") == "ready":
        logger.info("CLIP: already ready, skipping download.")
    else:
        try:
            logger.info("CLIP: downloading...")
            update_model_status(db, "clip", "downloading")
            ClipTagger().download()  # fetches ViT weights + CSV + .npy
            update_model_status(db, "clip", "ready")
            logger.info("CLIP: download complete.")
        except Exception as e:
            db.rollback()
            update_model_status(db, "clip", "error")
            logger.error(f"CLIP: download failed: {e}")

    # 3. Vision model (Qwen2-VL) — weights go to HuggingFace local cache
    from src.ai.vision import QwenVisionGenerator
    if get_model_status(db, "vision") == "ready":
        logger.info("Vision: already ready, skipping download.")
    else:
        try:
            update_model_status(db, "vision", "downloading")
            QwenVisionGenerator().download()
            update_model_status(db, "vision", "ready")
            logger.info("Vision: download complete.")
        except Exception as e:
            db.rollback()
            update_model_status(db, "vision", "error")
            logger.error(f"Vision: download failed: {e}")

    # 4. Nomic semantic embedder — weights go to HuggingFace local cache
    if get_model_status(db, "embedding") == "ready":
        logger.info("Nomic Embedder: already ready, skipping download.")
    else:
        try:
            update_model_status(db, "embedding", "downloading")
            from sentence_transformers import SentenceTransformer
            SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)
            update_model_status(db, "embedding", "ready")
            logger.info("Nomic Embedder: download complete.")
        except Exception as e:
            db.rollback()
            update_model_status(db, "embedding", "error")
            logger.error(f"Nomic Embedder: download failed: {e}")

    db.close()


@task_queue.task()
def metadata_task(photo_id: int, phase: str):
    """Extract metadata from photo and save it to the database."""
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        logger.info(f"Photo found in DB: {photo}")
        if photo:
            exif_raw = extract_exif(photo.file_path)
            logger.info(f"Photo exif_data: {exif_raw}")
            photo.captured_at = parse_datetime(exif_raw)
            logger.info(f"Photo captured_at: {photo.captured_at}")
            if exif_raw.get("Model") and exif_raw.get("Model") != "Unknown":
                make = exif_raw.get("Make")
                model = exif_raw.get("Model")
                if make and model and model != "Unknown":
                    logger.info(f"Photo make: {make}")
                    logger.info(f"Photo model: {model}")
                    camera = get_or_create_camera(
                        db, make=make, model=model
                    )
                    photo.camera_id = camera.id
                else:   
                    logger.info(f"Photo make or model not found")
            
            geo = GeoEnricher()
            geo_result = geo.geocode_photo(exif_raw)
            logger.info(f"Photo geoposition: {geo_result}")
            try:
                if geo_result["latitude"] and geo_result["longitude"]:
                    update_photo_geoposition(
                        db,
                        photo_id,
                        geo_result["latitude"],
                        geo_result["longitude"],
                        geo_result["address"]
                    )
                    logger.info(f"Updated photo geoposition")
            except Exception as e:
                logger.error(f"Failed to update photo geoposition: {e}")

            db.commit()
            logger.info(f"Photo updated: {photo.id}")
            finish_task(
                photo_id=photo_id, phase=phase, name="metadata_task"
            )
    except Exception as e:
        logger.error(f"Error in task for photo {photo_id}: {e}")
        delete_job(db, photo_id, phase)
    finally:
        db.close()


@task_queue.task()
def auto_tag_clip_task(photo_id: int, phase: str):
    logger.info(f"Auto-tagging photo: {photo_id}")
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        logger.info(f"Photo found in DB: {photo}")
        if photo:
            logger.info(f"Processing photo: {photo.file_path}")
            tagger = registry.clip_tagger
            logger.info(f"ID of tagger: {id(tagger)}")
            confident_tags = tagger.find_tags(photo.file_path)
            logger.info(f"Confident tags: {confident_tags}")
            # photo.keywords = [t for t, s in confident_tags]
            # logger.info(f"Photo keywords: {photo.keywords}")
            for tag_name, score in confident_tags:
                add_photo_tag_with_score(db, photo_id, tag_name, score)
                logger.info(f"Added tag: {tag_name} with score: {score}")
            finish_task(
                photo_id=photo_id, phase=phase, name="auto_tag_clip_task"
            )
    except Exception as e:
        logger.error(f"Error in task for photo {photo_id}: {e}")
        delete_job(db, photo_id, phase)
    finally:
        db.close()


@task_queue.task()
def categorize_photo_task(photo_id: int, phase: str):
    db = SessionLocal()
    try:
        photo = get_photo_by_id(db, photo_id)
        logger.info(f"Photo found in DB: {photo}")
        tagger = registry.clip_tagger
        logger.info(f"CLIP tagger: {tagger}")
        if photo:
            cat_results = tagger.categorize(photo.file_path)
            logger.info(f"Category results: {cat_results}")
            for cat_id, cat_name, score in cat_results:
                add_photo_category_with_score(db, photo_id, cat_id, score)
            finish_task(
                photo_id=photo_id, phase=phase, name="categorize_photo_task"
            )
    except Exception as e:
        logger.error(f"Error in task for photo {photo_id}: {e}")
        delete_job(db, photo_id, phase)
    finally:
        db.close()


@task_queue.task()
def vision_task(photo_id: int, phase: str):
    logger.info(f"Vision task for photo: {photo_id}")
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        logger.info(f"Photo found in DB: {photo}")
        if photo:
            generator = registry.vision_generator
            logger.info(f"Vision generator: {generator}")
            desc = generator.generate_vision_text(
                file_path=photo.file_path, prompt_key="describe_scene"
            )
            logger.info(f"Description: {desc}")
            photo.description = desc
            db.commit()
            logger.info(f"Photo updated: {photo}")
            finish_task(
                photo_id=photo_id, phase=phase, name="vision_task"
            )
    except Exception as e:
        logger.error(f"Error in task for photo {photo_id}: {e}")
        delete_job(db, photo_id, phase)
    finally:
        db.close()


@task_queue.task()
def ocr_task(photo_id: int, phase: str):
    """
    Performs OCR on the photo.
    """
    logger.info(f"OCR task for photo: {photo_id}")
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        logger.info(f"Photo found in DB: {photo}")
        if photo:
            text = extract_text_from_image(photo.file_path)
            logger.info(f"OCR text: {text}")
            if text and len(text.strip()) > 0:
                photo.ocr_text = text
                db.commit()
                logger.info(f"Photo updated: {photo}")
                is_this_document_task(photo_id, phase)
                logger.info("Started process to identify this image as a document")
            finish_task(
                photo_id=photo_id, phase=phase, name="ocr_task"
            )
    except Exception as e:
        logger.error(f"Error in task for photo {photo_id}: {e}")
        delete_job(db, photo_id, phase)
    finally:
        db.close()


@task_queue.task()
def is_this_document_task(photo_id: int, phase: str):
    """Refined check: Use Vision model to confirm if photo is a document."""
    db = SessionLocal()
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        if photo:
            gen = registry.vision_generator
            result = gen.generate_vision_text(
                photo.file_path, prompt_key="is_document"
            )
            logger.info(f"Is document result: {result}")
            # Simple binary conversion
            photo.is_doc = "yes" in result.lower()
            db.commit()
            finish_task(
                photo_id=photo_id, phase=phase, name="is_this_document_task"
            )
    except Exception as e:
        logger.error(f"Error in task for photo {photo_id}: {e}")
        delete_job(db, photo_id, phase)
    finally:
        db.close()
