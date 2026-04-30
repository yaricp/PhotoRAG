import pytesseract
from PIL import Image
from loguru import logger


def extract_text_from_image(filepath: str) -> str:
    """
    Extract text from an image.
    
    Args:
        filepath: Path to the image file.
    
    Returns:
        Text extracted from the image.
    """
    try:
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to extract text from image: {e}")
        return ""
