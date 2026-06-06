"""
API-level tests for /api/prompts/ endpoints.
Written before implementation (TDD).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db_service import seed_prompts_from_json
from src.deps import get_db
from src.main import app
from src.models import Base, Prompt

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

PROMPTS_JSON = Path(__file__).parent.parent / "prompts" / "prompts.json"


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db():
    """Set up the test DB override and seed prompts; restore after each test."""
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    db.query(Prompt).delete()
    db.commit()
    seed_prompts_from_json(db, PROMPTS_JSON)
    db.close()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


class TestGetPrompts:
    def test_returns_200(self, client):
        r = client.get("/api/prompts/")
        assert r.status_code == 200

    def test_returns_4_prompts(self, client):
        r = client.get("/api/prompts/")
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 4

    def test_sorted_by_key(self, client):
        r = client.get("/api/prompts/")
        keys = [p["key"] for p in r.json()]
        assert keys == sorted(keys)

    def test_each_prompt_has_required_fields(self, client):
        r = client.get("/api/prompts/")
        for p in r.json():
            assert "id" in p
            assert "key" in p
            assert "group" in p
            assert "name" in p
            assert "title" in p
            assert "text" in p
            assert "updated_at" in p


class TestUpdatePrompt:
    def test_returns_200_and_updated_text(self, client):
        r = client.put(
            "/api/prompts/vision_analysis.describe_scene",
            json={"text": "New describe text"},
        )
        assert r.status_code == 200
        assert r.json()["text"] == "New describe text"

    def test_persisted_in_subsequent_get(self, client):
        client.put(
            "/api/prompts/vision_analysis.is_document",
            json={"text": "Only answer true or false"},
        )
        r = client.get("/api/prompts/")
        p = next(x for x in r.json() if x["key"] == "vision_analysis.is_document")
        assert p["text"] == "Only answer true or false"

    def test_unknown_key_returns_404(self, client):
        r = client.put(
            "/api/prompts/nonexistent.key",
            json={"text": "something"},
        )
        assert r.status_code == 404

    def test_empty_text_rejected(self, client):
        r = client.put(
            "/api/prompts/vision_analysis.describe_scene",
            json={"text": "  "},
        )
        assert r.status_code == 422
