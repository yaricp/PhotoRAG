import easyocr
from loguru import logger


class EasyOCRReader:
    _instance = None
    _languages = None

    @classmethod
    def get_instance(cls, languages=None):
        if languages is None:
            languages = ['en', 'ru']
        
        # Пересоздаём если языки изменились
        if cls._instance is None or sorted(cls._languages) != sorted(languages):
            logger.info(f"Initializing EasyOCR Reader with languages: {languages}")
            cls._instance = easyocr.Reader(languages, gpu=False)
            cls._languages = languages
        
        return cls._instance


def extract_text_from_image(filepath: str, lang: str=None) -> str:
    """
    Extract text from an image using EasyOCR.

    Args:
        filepath: Path to the image file.
        lang: List of language codes (e.g., ['ru', 'en']).

    Returns:
        Text extracted from the image.
    """
    if lang is None:
        lang = ['ru', 'en']

    try:
        reader = EasyOCRReader.get_instance(lang)
        results = reader.readtext(filepath, detail=0)
        return " ".join(results).strip()

    except FileNotFoundError:
        logger.error(f"Image file not found: {filepath}")
        return ""
    except Exception as e:
        logger.error(f"Failed to extract text from image with EasyOCR: {e}")
        return ""
