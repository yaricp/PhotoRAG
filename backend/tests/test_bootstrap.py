# ATOMIC MOCK: Must happen before any project imports
import os

import pytest
import sqlalchemy.orm
import sqlalchemy.types
from sqlalchemy import create_engine

from src.db_service import get_all_model_states, update_model_status
from src.models import Base, ModelState

TEST_DB_FILE = "test_bootstrap.sqlite3"
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
    session.query(ModelState).delete()
    session.commit()
    session.close()


def test_update_model_status(db_session):
    # 1. Start downloading
    update_model_status(db_session, "clip", "downloading")
    states = get_all_model_states(db_session)
    assert len(states) == 1
    assert states[0].name == "clip"
    assert states[0].status == "downloading"

    # 2. Finish
    update_model_status(db_session, "clip", "ready")
    state = db_session.query(ModelState).filter_by(name="clip").first()
    assert state.status == "ready"
