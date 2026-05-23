from src.deps import get_db

def test_db_session_yields():
    generator = get_db()
    session = next(generator)
    assert session is not None
