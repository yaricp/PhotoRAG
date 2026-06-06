from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.deps import get_db
from src.main import app
from src.models import Base, Camera, Category, Geoposition, ModelState, Photo, Tag

# Setup Test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
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

    with (
        patch.object(registry.translator, "load"),
        patch.object(registry.translator, "translate", side_effect=lambda x, **kwargs: x),
    ):
        registry.translator._loaded = True
        yield


def test_folder_scanners_endpoint():
    response = client.post("/api/folder_scanners/", json={"path": "/mock/path"})
    assert response.status_code == 200
    assert response.json()["status"] == "started"


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
        hash="hash1",
        file_path="/mock/1.jpg",
        camera_id=cam.id,
        captured_at=datetime(2023, 1, 1),
        created_at=datetime(2023, 1, 1),
    )
    db.add(photo1)
    db.commit()

    geo = Geoposition(latitude=0.0, longitude=0.0)
    db.add(geo)
    db.commit()
    photo1.geoposition_id = geo.id
    db.commit()

    yield
    db.close()


def test_get_system_status():
    response = client.get("/api/system/status/")
    assert response.status_code == 200
    body = response.json()
    assert "ready" in body
    assert "chat_ready" in body
    assert isinstance(body["chat_ready"], bool)
    assert "models" in body


def test_system_status_chat_ready_false_when_model_not_loaded():
    from src.ai.registry import registry as _registry

    original = _registry._chat_model
    _registry._chat_model = None
    try:
        response = client.get("/api/system/status/")
        assert response.status_code == 200
        assert response.json()["chat_ready"] is False
    finally:
        _registry._chat_model = original


def test_system_status_chat_ready_true_when_model_loaded():
    from unittest.mock import MagicMock

    from src.ai.registry import registry as _registry

    original = _registry._chat_model
    _registry._chat_model = MagicMock()
    try:
        response = client.get("/api/system/status/")
        assert response.status_code == 200
        assert response.json()["chat_ready"] is True
    finally:
        _registry._chat_model = original


def test_get_folder_scanners():
    response = client.get("/api/folder_scanners/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_models_endpoints():
    # init defaults
    from src.db_service import init_default_model_configs

    db = TestingSessionLocal()
    init_default_model_configs(db)
    db.close()

    # get models
    response = client.get("/api/models/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 6

    # update model
    update_data = {"mode": "remote", "model_name": "test-model", "url": "http://test", "api_key": "123"}

    # mode=remote → no warmup task dispatched
    response = client.put("/api/models/vision", json=update_data)
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "remote"
    assert result["url"] == "http://test"


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
