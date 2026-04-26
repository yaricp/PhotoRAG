from src.models import Photo

def test_photo_model_instantiation():
    photo = Photo(file_path="/test/path.jpg", hash="12345", status="pending")
    assert photo.file_path == "/test/path.jpg"
    assert photo.status == "pending"
