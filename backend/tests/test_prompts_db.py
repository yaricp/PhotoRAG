"""
Tests for the Prompt DB model and db_service helpers.
Written before implementation (TDD).
"""
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    yield session
    session.query(Prompt).delete()
    session.commit()
    session.close()


# ---------------------------------------------------------------------------
# seed_prompts_from_json
# ---------------------------------------------------------------------------

class TestSeedPromptsFromJson:
    def test_creates_4_rows(self, db):
        from src.db_service import seed_prompts_from_json
        count = seed_prompts_from_json(db, PROMPTS_JSON)
        assert count == 4
        assert db.query(Prompt).count() == 4

    def test_rows_have_correct_keys(self, db):
        from src.db_service import seed_prompts_from_json
        seed_prompts_from_json(db, PROMPTS_JSON)
        keys = {p.key for p in db.query(Prompt).all()}
        assert keys == {
            "vision_analysis.system_prompt",
            "vision_analysis.describe_scene",
            "vision_analysis.is_document",
            "chat_agent.system_message",
        }

    def test_idempotent_second_call_adds_no_rows(self, db):
        from src.db_service import seed_prompts_from_json
        seed_prompts_from_json(db, PROMPTS_JSON)
        count2 = seed_prompts_from_json(db, PROMPTS_JSON)
        assert count2 == 0
        assert db.query(Prompt).count() == 4

    def test_idempotent_does_not_overwrite_user_edits(self, db):
        from src.db_service import seed_prompts_from_json, update_prompt
        seed_prompts_from_json(db, PROMPTS_JSON)
        update_prompt(db, "vision_analysis.describe_scene", "My custom prompt text")
        seed_prompts_from_json(db, PROMPTS_JSON)
        p = db.query(Prompt).filter_by(key="vision_analysis.describe_scene").first()
        assert p.text == "My custom prompt text"

    def test_group_and_name_populated(self, db):
        from src.db_service import seed_prompts_from_json
        seed_prompts_from_json(db, PROMPTS_JSON)
        p = db.query(Prompt).filter_by(key="vision_analysis.describe_scene").first()
        assert p.group == "vision_analysis"
        assert p.name == "describe_scene"
        assert p.title  # non-empty

    def test_text_matches_json(self, db):
        import json
        from src.db_service import seed_prompts_from_json
        seed_prompts_from_json(db, PROMPTS_JSON)
        raw = json.loads(PROMPTS_JSON.read_text())
        p = db.query(Prompt).filter_by(key="chat_agent.system_message").first()
        assert p.text == raw["chat_agent"]["system_message"]


# ---------------------------------------------------------------------------
# get_all_prompts
# ---------------------------------------------------------------------------

class TestGetAllPrompts:
    def test_returns_sorted_list(self, db):
        from src.db_service import seed_prompts_from_json, get_all_prompts
        seed_prompts_from_json(db, PROMPTS_JSON)
        prompts = get_all_prompts(db)
        assert len(prompts) == 4
        # sorted by group then name
        keys = [p.key for p in prompts]
        assert keys == sorted(keys)

    def test_empty_db_returns_empty_list(self, db):
        from src.db_service import get_all_prompts
        assert get_all_prompts(db) == []


# ---------------------------------------------------------------------------
# get_prompt_by_key
# ---------------------------------------------------------------------------

class TestGetPromptByKey:
    def test_returns_prompt(self, db):
        from src.db_service import seed_prompts_from_json, get_prompt_by_key
        seed_prompts_from_json(db, PROMPTS_JSON)
        p = get_prompt_by_key(db, "vision_analysis.is_document")
        assert p is not None
        assert p.key == "vision_analysis.is_document"

    def test_unknown_key_returns_none(self, db):
        from src.db_service import seed_prompts_from_json, get_prompt_by_key
        seed_prompts_from_json(db, PROMPTS_JSON)
        assert get_prompt_by_key(db, "nonexistent.key") is None


# ---------------------------------------------------------------------------
# update_prompt
# ---------------------------------------------------------------------------

class TestUpdatePrompt:
    def test_changes_text(self, db):
        from src.db_service import seed_prompts_from_json, update_prompt, get_prompt_by_key
        seed_prompts_from_json(db, PROMPTS_JSON)
        updated = update_prompt(db, "vision_analysis.system_prompt", "Brand new text")
        assert updated is not None
        assert updated.text == "Brand new text"
        # persisted
        fresh = get_prompt_by_key(db, "vision_analysis.system_prompt")
        assert fresh.text == "Brand new text"

    def test_unknown_key_returns_none(self, db):
        from src.db_service import update_prompt
        result = update_prompt(db, "bad.key", "text")
        assert result is None

    def test_updates_updated_at(self, db):
        import time
        from src.db_service import seed_prompts_from_json, update_prompt, get_prompt_by_key
        seed_prompts_from_json(db, PROMPTS_JSON)
        before = get_prompt_by_key(db, "vision_analysis.system_prompt").updated_at
        time.sleep(0.01)
        update_prompt(db, "vision_analysis.system_prompt", "Changed")
        after = get_prompt_by_key(db, "vision_analysis.system_prompt").updated_at
        assert after >= before
