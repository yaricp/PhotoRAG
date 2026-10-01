"""Tag results must remain idempotent when retries overlap at the database boundary."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src import models


def test_duplicate_model_labels_are_normalized_and_keep_the_highest_score(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'duplicate-tags.db'}")
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        photo = models.Photo(hash="duplicate-photo", file_path="/duplicate.jpg")
        tag = models.Tag(name="existing")
        db.add_all([photo, tag])
        db.commit()
        photo_id = photo.id

    from src.tasks import clip_tasks

    monkeypatch.setattr(clip_tasks, "SessionLocal", factory)
    clip_tasks._save_tags_sync(
        photo_id,
        [("existing", 0.5), (" existing ", 0.9), ("EXISTING", 0.7)],
    )

    with factory() as db:
        tags = db.query(models.Tag).all()
        links = db.query(models.PhotoTag).filter_by(photo_id=photo_id).all()
        assert [tag.name for tag in tags] == ["existing"]
        assert len(links) == 1
        assert links[0].confidence_score == 0.9
    engine.dispose()


def test_concurrent_tag_retries_do_not_insert_duplicate_photo_tag(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'tags.db'}", connect_args={"timeout": 1})

    @event.listens_for(engine, "connect")
    def enable_wal(connection, _record):
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=1000")

    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        photo = models.Photo(hash="same-photo", file_path="/same.jpg")
        tag = models.Tag(name="existing")
        db.add_all([photo, tag])
        db.commit()
        photo_id = photo.id

    from src.tasks import clip_tasks

    monkeypatch.setattr(clip_tasks, "SessionLocal", factory)
    original_add_tag = clip_tasks.add_photo_tag_with_score
    first_write_checked = Event()
    release_first_write = Event()
    second_write_checked = Event()
    calls_lock = Lock()
    call_count = 0

    def pause_after_check(db, photo_id, tag_name, score, *, commit=True):
        nonlocal call_count
        association = original_add_tag(db, photo_id, tag_name, score, commit=commit)
        with calls_lock:
            call_count += 1
            this_call = call_count
        if this_call == 1:
            first_write_checked.set()
            assert release_first_write.wait(timeout=5)
        else:
            second_write_checked.set()
        return association

    monkeypatch.setattr(clip_tasks, "add_photo_tag_with_score", pause_after_check)

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(clip_tasks._save_tags_sync, photo_id, [("existing", 0.75)])
        assert first_write_checked.wait(timeout=5)
        second = workers.submit(clip_tasks._save_tags_sync, photo_id, [("existing", 0.75)])
        second_was_serialized = not second_write_checked.wait(timeout=0.1)
        release_first_write.set()
        first.result(timeout=10)
        second.result(timeout=10)
        assert second_was_serialized, "a concurrent retry read the photo-tag link before the first write committed"

    with factory() as db:
        links = db.query(models.PhotoTag).filter_by(photo_id=photo_id).all()
        assert len(links) == 1
        assert links[0].confidence_score == 0.75

    engine.dispose()
