import pytest
import sys
from unittest.mock import MagicMock, patch
import sqlalchemy.types
import numpy as np

# ATOMIC MOCK
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy
sys.modules['open_clip'] = MagicMock()
sys.modules['torch'] = MagicMock()

import sqlalchemy.orm
import os
from sqlalchemy import create_engine
from src.models import Base, Photo, Category, PhotoCategory
from src.db_service import add_photo_category_with_score, get_all_categories
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
    
    add_photo_category_with_score(db_session, photo.id, "Nature", 0.88)
    
    pc = db_session.query(PhotoCategory).filter_by(photo_id=photo.id).first()
    assert pc.category.name == "Nature"
    assert pc.confidence_score == 0.88

@patch('src.ai.clip.open_clip')
def test_clip_categorize_logic(mock_open_clip, tmp_path):
    tagger = ClipTagger()
    tagger.model = MagicMock()
    tagger.preprocess = MagicMock()
    tagger.device = "cpu"
    
    # Mock Image & Text Features
    mock_img_feat = MagicMock()
    mock_img_feat.norm.return_value = 1.0
    # Division result
    mock_img_norm = MagicMock()
    mock_raw_feat = MagicMock()
    mock_raw_feat.__truediv__.return_value = mock_img_norm
    mock_img_norm.cpu.return_value.numpy.return_value = np.array([[1.0, 0.0]]) # 1x2 fake feat
    tagger.model.encode_image.return_value = mock_raw_feat
    
    # Mock text features (2 categories)
    mock_text_feat = MagicMock()
    mock_text_feat.__itruediv__.return_value = mock_text_feat
    mock_text_feat.cpu.return_value.numpy.return_value = np.array([[1.0, 0.0], [0.0, 1.0]]) # 2x2 identity
    tagger.model.encode_text.return_value = mock_text_feat
    
    with patch('PIL.Image.open', return_value=MagicMock()):
        with patch.object(tagger, 'load', return_value=None):
            results = tagger.categorize("fake.jpg", ["Nature", "Urban"])
            assert len(results) == 2
            assert results[0][0] == "Nature"
            assert isinstance(results[0][1], float)
