"""
API tests for POST /api/photos/{id}/reindex.
Written before implementation (TDD).
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, AsyncMock
from datetime import datetime

from src.main import app
from src.deps import get_db
from src.models import Base, Photo

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def photo_with_description():
    db = TestingSessionLocal()
    p = Photo(hash=uuid.uuid4().hex, file_path="/test/reindex1.jpg",
              description="A beautiful mountain lake", created_at=datetime.utcnow())
    db.add(p)
    db.commit()
    photo_id = p.id
    db.close()
    return photo_id


@pytest.fixture
def photo_no_description():
    db = TestingSessionLocal()
    p = Photo(hash=uuid.uuid4().hex, file_path="/test/reindex2.jpg",
              description=None, created_at=datetime.utcnow())
    db.add(p)
    db.commit()
    photo_id = p.id
    db.close()
    return photo_id


class TestReindexEndpoint:
    @patch("src.main.final_embedding_task", new_callable=AsyncMock)
    def test_returns_200_and_queued_status(self, _mock, client, photo_with_description):
        r = client.post(f"/api/photos/{photo_with_description}/reindex")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "queued"
        assert data["photo_id"] == photo_with_description

    @patch("src.main.final_embedding_task", new_callable=AsyncMock)
    def test_returns_404_for_unknown_photo(self, _mock, client):
        r = client.post("/api/photos/99999/reindex")
        assert r.status_code == 404

    @patch("src.main.final_embedding_task", new_callable=AsyncMock)
    def test_queues_even_without_description(self, _mock, client, photo_no_description):
        # Endpoint does not validate description — task handles it gracefully
        r = client.post(f"/api/photos/{photo_no_description}/reindex")
        assert r.status_code == 200
        assert r.json()["status"] == "queued"

    @patch("src.main.final_embedding_task", new_callable=AsyncMock)
    def test_task_called_with_photo_id(self, mock_task, client, photo_with_description):
        client.post(f"/api/photos/{photo_with_description}/reindex")
        mock_task.assert_called_once_with(photo_with_description)
