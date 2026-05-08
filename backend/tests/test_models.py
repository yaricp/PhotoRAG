from src.models import Photo, Tag, Person, Keyword, Category, Camera, Geoposition, AIModelConfig

def test_photo_model_basic():
    photo = Photo(file_path="/test/path.jpg", hash="12345")
    assert photo.file_path == "/test/path.jpg"
    assert photo.hash == "12345"

def test_tag_model_basic():
    tag = Tag(name="Nature")
    assert tag.name == "Nature"

def test_person_model_basic():
    person = Person(name="John Doe")
    assert person.name == "John Doe"

def test_keyword_model_basic():
    kw = Keyword(name="Mountains")
    assert kw.name == "Mountains"

def test_category_model_basic():
    cat = Category(name="Landscape")
    assert cat.name == "Landscape"

def test_camera_model_basic():
    cam = Camera(make="Sony", model="A7 III", serial_number="SN12345")
    assert cam.make == "Sony"
    assert cam.model == "A7 III"
    assert cam.serial_number == "SN12345"

def test_geoposition_model_basic():
    geo = Geoposition(latitude=45.523062, longitude=-122.676482, address="Portland, OR")
    assert geo.latitude == 45.523062
    assert geo.longitude == -122.676482
    assert geo.address == "Portland, OR"

def test_ai_model_config_basic():
    config = AIModelConfig(
        type="vision",
        mode="remote",
        model_name="gpt-4o",
        url="https://api.openai.com",
        api_key="secret"
    )
    assert config.type == "vision"
    assert config.mode == "remote"
    assert config.model_name == "gpt-4o"
    assert config.api_key == "secret"
