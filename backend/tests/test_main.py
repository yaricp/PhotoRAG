from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.main import app
from src.database import get_db
from src.models import Base, Photo, Tag, Category, Camera, Geoposition, ModelState
from datetime import datetime
import pytest
from unittest.mock import patch

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_translator():
    from src.ai.registry import registry
    with patch.object(registry.translator, 'load'), \
         patch.object(registry.translator, 'translate', side_effect=lambda x, **kwargs: x):
        registry.translator._loaded = True
        yield

def test_watch_endpoint():
    response = client.post("/api/watch/", json={"path": "/mock/path"})
    assert response.status_code == 200
    assert response.json()["status"] == "watching"

@pytest.fixture(autouse=True)
def setup_data():
    db = TestingSessionLocal()
    # clear db
    db.query(Photo).delete()
    db.query(Tag).delete()
    db.query(Category).delete()
    db.query(Camera).delete()
    db.query(Geoposition).delete()
    db.query(ModelState).delete()
    
    # insert models
    cam = Camera(make="Sony", model="A7")
    db.add(cam)
    tag = Tag(name="Nature")
    db.add(tag)
    cat = Category(name="Landscape")
    db.add(cat)
    db.commit()
    
    photo1 = Photo(
        hash="hash1", file_path="/mock/1.jpg", 
        camera_id=cam.id,
        captured_at=datetime(2023, 1, 1),
        created_at=datetime(2023, 1, 1)
    )
    db.add(photo1)
    db.commit()
    
    geo = Geoposition(photo_id=photo1.id, latitude=0.0, longitude=0.0)
    db.add(geo)
    db.commit()
    
    yield
    db.close()


def test_get_system_status():
    response = client.get("/api/system/status/")
    assert response.status_code == 200
    assert "ready" in response.json()


def test_get_watchers():
    response = client.get("/api/watchers/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_photo_by_id():
    db = TestingSessionLocal()
    photo = db.query(Photo).first()
    db.close()
    
    response = client.get(f"/api/photos/{photo.id}")
    assert response.status_code == 200
    assert response.json()["id"] == photo.id


def test_get_photos_pagination_and_filtering():
    response = client.get("/api/photos/?limit=10&skip=0")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert len(data["items"]) == 1


def test_metadata_endpoints():
    endpoints = ["/api/tags/", "/api/categories/", "/api/cameras/", "/api/geopositions/"]
    for ep in endpoints:
        response = client.get(ep)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1


@patch("src.main.get_photos_by_vector")
def test_search_photos(mock_get):
    mock_get.return_value = []
    response = client.post("/api/search/", json={"text_query": "dog", "k": 10, "thresholds": 0.5})
    assert response.status_code == 200
