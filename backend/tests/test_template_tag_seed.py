import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_default_tags_seed_file_is_bundled():
    path = Path(__file__).resolve().parents[1] / "defaults" / "default_tags.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "dog" in data
    assert "cat" in data
    assert len(data) > 100


def test_seed_template_vocabularies_uses_default_tags_when_data_dir_is_missing(db):
    from src.install import seed_template_vocabularies
    from src.models import TemplateTag

    with patch("src.install._bundled_data_path", return_value="/missing/tags_names.json"):
        seed_template_vocabularies(db)

    names = {row.name for row in db.query(TemplateTag).all()}
    assert "dog" in names
    assert "cat" in names


def test_remote_clip_name_loader_uses_default_tags_when_cache_and_db_are_empty(db):
    from src.model_services import _load_clip_names

    with patch("src.db.database.SessionLocal", return_value=db):
        names = _load_clip_names("/missing/appdata/tags_names.json", "tags")

    assert "dog" in names
    assert "cat" in names
    assert len(names) > 100
