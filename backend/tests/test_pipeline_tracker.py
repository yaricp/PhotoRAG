"""
TDD tests for src/pipeline_tracker.py.

Uses an in-memory SQLite database to avoid touching the production DB.
SessionLocal is monkeypatched to use the test engine.
"""

import sys
from unittest.mock import MagicMock

import sqlalchemy.types

# Mock pgvector before any src.* import so models.py doesn't fail
mock_pgvector = MagicMock()
mock_pgvector.sqlalchemy.Vector = lambda size: sqlalchemy.types.JSON()
sys.modules.setdefault("pgvector", mock_pgvector)
sys.modules.setdefault("pgvector.sqlalchemy", mock_pgvector.sqlalchemy)

# Mock sqlite_vec so src.db.database can be imported in the test environment
sys.modules.setdefault("sqlite_vec", MagicMock())

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Photo, PipelineTask

TEST_ENGINE = create_engine("sqlite:///:memory:")
TestSessionFactory = sessionmaker(bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def setup_schema():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db():
    session = TestSessionFactory()
    yield session
    session.close()


@pytest.fixture
def photo(db) -> Photo:
    """Minimal Photo row for FK references."""
    p = Photo(file_path="/tmp/test.jpg", hash="abc123")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def patch_session(monkeypatch):
    """Replace SessionLocal in pipeline_tracker with the test factory."""
    monkeypatch.setattr("src.pipeline_tracker.SessionLocal", TestSessionFactory)


# ---------------------------------------------------------------------------
# init_pipeline_tasks
# ---------------------------------------------------------------------------


class TestInitPipelineTasks:
    def test_creates_pending_records(self, photo, patch_session):
        from src.pipeline_tracker import init_pipeline_tasks

        init_pipeline_tasks(photo.id, "phase_1", ["metadata_task", "auto_tag_clip_task"])

        db = TestSessionFactory()
        tasks = db.query(PipelineTask).filter_by(photo_id=photo.id).all()
        db.close()

        assert len(tasks) == 2
        names = {t.task_name for t in tasks}
        assert names == {"metadata_task", "auto_tag_clip_task"}
        assert all(t.status == "pending" for t in tasks)
        assert all(t.phase == "phase_1" for t in tasks)

    def test_empty_task_list_creates_nothing(self, photo, patch_session):
        from src.pipeline_tracker import init_pipeline_tasks

        init_pipeline_tasks(photo.id, "phase_1", [])

        db = TestSessionFactory()
        count = db.query(PipelineTask).count()
        db.close()
        assert count == 0


# ---------------------------------------------------------------------------
# track_task — success path
# ---------------------------------------------------------------------------


class TestTrackTaskSuccess:
    @pytest.mark.asyncio
    async def test_marks_running_then_done(self, photo, patch_session):
        from src.pipeline_tracker import init_pipeline_tasks, track_task

        init_pipeline_tasks(photo.id, "phase_1", ["metadata_task"])

        async with track_task(photo.id, "phase_1", "metadata_task"):
            db = TestSessionFactory()
            mid = db.query(PipelineTask).filter_by(photo_id=photo.id, task_name="metadata_task").first()
            db.close()
            assert mid.status == "running"
            assert mid.started_at is not None

        db = TestSessionFactory()
        final = db.query(PipelineTask).filter_by(photo_id=photo.id, task_name="metadata_task").first()
        db.close()
        assert final.status == "done"
        assert final.finished_at is not None
        assert final.error is None

    @pytest.mark.asyncio
    async def test_started_at_before_finished_at(self, photo, patch_session):
        from src.pipeline_tracker import init_pipeline_tasks, track_task

        init_pipeline_tasks(photo.id, "phase_1", ["auto_tag_clip_task"])
        async with track_task(photo.id, "phase_1", "auto_tag_clip_task"):
            pass

        db = TestSessionFactory()
        task = db.query(PipelineTask).filter_by(task_name="auto_tag_clip_task").first()
        db.close()
        assert task.started_at <= task.finished_at


# ---------------------------------------------------------------------------
# track_task — failure path
# ---------------------------------------------------------------------------


class TestTrackTaskFailure:
    @pytest.mark.asyncio
    async def test_marks_failed_and_stores_error(self, photo, patch_session):
        from src.pipeline_tracker import init_pipeline_tasks, track_task

        init_pipeline_tasks(photo.id, "phase_1", ["vision_task"])

        with pytest.raises(ValueError, match="model exploded"):
            async with track_task(photo.id, "phase_1", "vision_task"):
                raise ValueError("model exploded")

        db = TestSessionFactory()
        task = db.query(PipelineTask).filter_by(task_name="vision_task").first()
        db.close()
        assert task.status == "failed"
        assert "model exploded" in task.error
        assert task.finished_at is not None

    @pytest.mark.asyncio
    async def test_exception_is_reraised(self, photo, patch_session):
        from src.pipeline_tracker import init_pipeline_tasks, track_task

        init_pipeline_tasks(photo.id, "phase_1", ["clip_task"])

        with pytest.raises(RuntimeError):
            async with track_task(photo.id, "phase_1", "clip_task"):
                raise RuntimeError("worker crashed")


# ---------------------------------------------------------------------------
# track_task — graceful no-op when record missing
# ---------------------------------------------------------------------------


class TestTrackTaskNoRecord:
    @pytest.mark.asyncio
    async def test_does_not_crash_when_task_not_initialized(self, photo, patch_session):
        """If init_pipeline_tasks was never called, track_task should be a no-op."""
        from src.pipeline_tracker import track_task

        async with track_task(photo.id, "phase_1", "nonexistent_task"):
            pass  # should not raise


# ---------------------------------------------------------------------------
# get_active_pipeline_tasks
# ---------------------------------------------------------------------------


class TestGetActivePipelineTasks:
    def test_returns_pending_and_running(self, photo, db, patch_session):
        from src.pipeline_tracker import get_active_pipeline_tasks, init_pipeline_tasks

        init_pipeline_tasks(photo.id, "phase_1", ["task_a", "task_b"])
        # manually set one to done
        inner = TestSessionFactory()
        t = inner.query(PipelineTask).filter_by(task_name="task_a").first()
        t.status = "done"
        inner.commit()
        inner.close()

        results = get_active_pipeline_tasks(db)
        assert len(results) == 1
        assert results[0].task_name == "task_b"

    def test_excludes_done_and_failed(self, photo, db, patch_session):
        from src.pipeline_tracker import get_active_pipeline_tasks, init_pipeline_tasks

        init_pipeline_tasks(photo.id, "phase_1", ["t1", "t2"])
        inner = TestSessionFactory()
        for name in ["t1", "t2"]:
            t = inner.query(PipelineTask).filter_by(task_name=name).first()
            t.status = "failed"
        inner.commit()
        inner.close()

        results = get_active_pipeline_tasks(db)
        assert results == []


# ---------------------------------------------------------------------------
# get_photo_pipeline_tasks
# ---------------------------------------------------------------------------


class TestGetPhotoPipelineTasks:
    def test_returns_tasks_for_photo(self, photo, db, patch_session):
        from src.pipeline_tracker import get_photo_pipeline_tasks, init_pipeline_tasks

        init_pipeline_tasks(photo.id, "phase_1", ["meta", "clip"])

        results = get_photo_pipeline_tasks(db, photo.id)
        assert len(results) == 2

    def test_does_not_return_other_photos_tasks(self, photo, db, patch_session):
        from src.pipeline_tracker import get_photo_pipeline_tasks, init_pipeline_tasks

        # Create second photo
        p2 = Photo(file_path="/tmp/other.jpg", hash="def456")
        db.add(p2)
        db.commit()
        db.refresh(p2)

        init_pipeline_tasks(photo.id, "phase_1", ["task_x"])
        init_pipeline_tasks(p2.id, "phase_1", ["task_y"])

        results = get_photo_pipeline_tasks(db, photo.id)
        assert len(results) == 1
        assert results[0].task_name == "task_x"
