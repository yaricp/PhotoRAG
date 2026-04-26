from src.ai.factory import ModelFactory
from src.config import Settings

def test_model_factory_identifies_local():
    factory = ModelFactory(Settings())
    assert factory.is_local_mode == True
