import pytest
import os
import shutil
import time
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo, ProcessingJob, ModelState
from src.db.database import SessionLocal
from src.observer import PhotoEventHandler
from src.tasks.utils import phase_logic, _dispatch_tasks
import src.queues.clip_queue
import src.queues.vision_queue
import src.queues.embedding_queue

# Mock the registry to avoid loading heavy models during E2E test
# but return realistic values for our doc1.png
@pytest.fixture(autouse=True)
def mock_ai_registry():
    # 1. Prepare mocks for the components
    mock_tagger = MagicMock()
    mock_tagger.find_tags.return_value = [("document", 0.9), ("text", 0.8), ("paper", 0.7), ("official", 0.6)]
    mock_tagger.categorize.return_value = [(1, "documents", 0.95)]
    mock_embedder = MagicMock()
    type(mock_embedder).name = PropertyMock(return_value="nomic-ai/nomic-embed-text-v1.5")
    
    def vision_side_effect(*args, **kwargs):
        pk = kwargs.get("prompt_key") or (args[1] if len(args) > 1 else None)
        return "Yes" if pk == "is_document" else "A formal text document, likely an invoice or contract."
    
    # 2. Patch the registry in each task module to ensure they use our mocks
    with patch('src.tasks.clip_tasks.registry') as m_clip_reg, \
         patch('src.tasks.vision_tasks.registry') as m_vis_reg, \
         patch('src.tasks.embedding_tasks.registry') as m_emb_reg, \
         patch('src.ai.registry.registry') as m_ai_reg:
        
        # Configure mocks
        for m in [m_clip_reg, m_vis_reg, m_emb_reg, m_ai_reg]:
            m.clip_tagger = mock_tagger
            m.nomic_embedder = mock_embedder
            m.generate_vision_text.side_effect = vision_side_effect
            m.embedder_encode_text.return_value = [0.1] * 768
        
        # 3. Patch OCR
        with patch('src.tasks.vision_tasks.extract_text_from_image') as mock_ocr:
            mock_ocr.return_value = "INVOICE #999\nDate: 2024-01-01\nTotal: $500.00\nThis is a sample document for E2E testing."
            yield registry

@pytest.fixture
def test_db():
    TEST_DB_URL = "sqlite:///./test_e2e.sqlite3"
    engine = create_engine(TEST_DB_URL)
    TestingSessionLocal = sessionmaker(bind=engine)
    
    Base.metadata.create_all(bind=engine)
    
    # Initialize model states as ready so pipeline doesn't wait
    db = TestingSessionLocal()
    for mname in ["clip", "vision", "embedding", "ocr", "translator"]:
        db.add(ModelState(name=mname, status="ready"))
    db.commit()
    db.close()
    
    yield TestingSessionLocal
    
    if os.path.exists("./test_e2e.sqlite3"):
        os.remove("./test_e2e.sqlite3")

@pytest.fixture
def watch_dir(tmp_path):
    d = tmp_path / "watch"
    d.mkdir()
    return d

def test_full_pipeline_e2e(test_db, watch_dir):
    """
    Test full pipeline from Observer to DB results.
    """
    # 1. Patch dependencies to use test DB
    with patch('src.observer.SessionLocal', test_db), \
         patch('src.tasks.utils.SessionLocal', test_db), \
         patch('src.tasks.clip_tasks.SessionLocal', test_db), \
         patch('src.tasks.vision_tasks.SessionLocal', test_db), \
         patch('src.tasks.embedding_tasks.SessionLocal', test_db), \
         patch('src.tasks.SessionLocal', test_db):

        # Force immediate execution for all queues
        old_clip_imm = src.queues.clip_queue.clip_queue.immediate
        old_vision_imm = src.queues.vision_queue.vision_queue.immediate
        old_emb_imm = src.queues.embedding_queue.embedding_queue.immediate
        
        src.queues.clip_queue.clip_queue.immediate = True
        src.queues.vision_queue.vision_queue.immediate = True
        src.queues.embedding_queue.embedding_queue.immediate = True

        try:
            db = test_db()
            # 2. Setup event handler
            handler = PhotoEventHandler()
            
            # 3. Prepare real photo
            src_photo = "./Pictures/doc1.png"
            if not os.path.exists(src_photo):
                pytest.skip("doc1.png not found in Pictures/")
                
            dst_photo = watch_dir / "doc1.png"
            shutil.copy(src_photo, dst_photo)
            
            # 4. Simulate Observer event
            class MockEvent:
                src_path = str(dst_photo)
                is_directory = False
                
            handler.on_created(MockEvent())
            
            # Refresh photo from DB to get latest results
            photo = db.query(Photo).filter(Photo.file_path == str(dst_photo)).first()
            assert photo is not None, "Photo record should be created"
            
            print(f"DEBUG: photo.description={photo.description}")
            print(f"DEBUG: photo.is_doc={photo.is_doc}")
            print(f"DEBUG: photo.ocr_text={photo.ocr_text}")
            
            assert photo.description == "A formal text document, likely an invoice or contract."
            assert photo.is_doc is True, f"Document detection should work, got {photo.is_doc}"
            assert "INVOICE #999" in photo.ocr_text, "OCR text should be saved"
            
            # Check tags
            tag_names = [t.tag.name for t in photo.tags_rel]
            assert "document" in tag_names
            
            # Check categories
            cat_names = [c.category.name for c in photo.categories_rel]
            assert "documents" in cat_names
            
            # Check if job was cleaned up
            remaining_jobs = db.query(ProcessingJob).filter(ProcessingJob.photo_id == photo.id).count()
            assert remaining_jobs == 0, "All jobs should be finished and deleted"
            
        finally:
            src.queues.clip_queue.clip_queue.immediate = old_clip_imm
            src.queues.vision_queue.vision_queue.immediate = old_vision_imm
            src.queues.embedding_queue.embedding_queue.immediate = old_emb_imm
            db.close()
