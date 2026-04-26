import sys
from unittest.mock import MagicMock
import sqlalchemy.types

# ATOMIC MOCK
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules['pgvector'] = mock_pgvector
sys.modules['pgvector.sqlalchemy'] = mock_pgvector.sqlalchemy

import pytest
import sqlalchemy.orm
import os
from sqlalchemy import create_engine
from src.models import Base, Photo, Tag, Person, Keyword, Category, Camera, Geoposition

TEST_DB_FILE = "test_relational.sqlite3"
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
    # Clear all tables
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()

def test_photo_camera_relationship(db_session):
    camera = Camera(model="Sony A7 IV", make="Sony")
    db_session.add(camera)
    db_session.commit()
    
    photo = Photo(hash="hash1", file_path="test.jpg", camera_id=camera.id)
    db_session.add(photo)
    db_session.commit()
    
    assert photo.camera.model == "Sony A7 IV"
    assert len(camera.photos) == 1

def test_photo_keyword_many_to_many(db_session):
    kw1 = Keyword(name="mountain")
    kw2 = Keyword(name="snow")
    photo = Photo(hash="hash2", file_path="hike.jpg")
    
    photo.keywords_rel.append(kw1)
    photo.keywords_rel.append(kw2)
    db_session.add(photo)
    db_session.commit()
    
    assert len(photo.keywords_rel) == 2
    assert photo.keywords_rel[0].name == "mountain"

def test_photo_geoposition_one_to_one(db_session):
    photo = Photo(hash="hash3", file_path="gps.jpg")
    db_session.add(photo)
    db_session.commit()
    
    geo = Geoposition(photo_id=photo.id, latitude=48.8566, longitude=2.3522)
    db_session.add(geo)
    db_session.commit()
    
    assert photo.geoposition.latitude == 48.8566
    assert geo.photo.hash == "hash3"
