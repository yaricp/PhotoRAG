import pytest
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types
import numpy as np

# ATOMIC MOCK
sys.modules['open_clip'] = MagicMock()


import sqlalchemy.orm
import os
from sqlalchemy import create_engine
from src.models import Base, Photo, Category, PhotoCategory
from src.db_service import add_photo_category_with_score, get_or_create_category
from src.ai.clip import ClipTagger

TEST_DB_FILE = "test_categories_scored.sqlite3"
test_engine = create_engine(f"sqlite:///{TEST_DB_FILE}")

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    Base.metadata.create_all(bind=test_engine)
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)

TestSessionLocal = sqlalchemy.orm.sessionmaker(bind=test_engine)

@pytest.fixture
def db_session():
    session = TestSessionLocal()
    yield session
    session.query(PhotoCategory).delete()
    session.query(Photo).delete()
    session.query(Category).delete()
    session.commit()
    session.close()

def test_category_persistence_with_score(db_session):
    photo = Photo(hash="cat_hash", file_path="cat.jpg")
    db_session.add(photo)
    db_session.commit()
    
    cat = get_or_create_category(db_session, "Nature")
    
    add_photo_category_with_score(db_session, photo.id, cat.id, 0.88)
    
    pc = db_session.query(PhotoCategory).filter_by(photo_id=photo.id).first()
    assert pc.category.name == "Nature"
    assert pc.confidence_score == 0.88

@patch('src.ai.clip.SessionLocal')
@patch('src.ai.clip.open_clip')
def test_clip_categorize_logic(mock_open_clip, mock_session, tmp_path):
    import torch
    # Mock db to return categories
    mock_db = mock_session.return_value
    mock_cat1 = MagicMock(id=1, name="Nature", prompt="Nature")
    mock_cat2 = MagicMock(id=2, name="Urban", prompt="Urban")
    
    with patch('src.ai.clip.get_all_categories', return_value=[mock_cat1, mock_cat2]):
        tagger = ClipTagger()
        tagger.model = MagicMock()
        tagger.preprocess = MagicMock()
        tagger.device = "cpu"
        
        # Use real PyTorch tensors to bypass MagicMock math issues
        # Image feature matches first category (Nature)
        mock_img_feat = torch.tensor([[1.0, 0.0]])
        tagger.model.encode_image.return_value = mock_img_feat
        tagger.categories_features = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
        
        with patch('PIL.Image.open', return_value=MagicMock()):
            with patch.object(tagger, 'load_model', return_value=None):
                with patch.object(tagger, 'load_or_compute_categories', return_value=None):
                    tagger.categories = [{"id": 1, "name": "Nature"}, {"id": 2, "name": "Urban"}]
                    results = tagger.categorize("fake.jpg")
                    assert len(results) == 1
                    assert results[0][0] == 1
                    assert results[0][1] == "Nature"
                    assert isinstance(results[0][2], float)
