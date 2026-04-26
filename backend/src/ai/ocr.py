import pytesseract
from PIL import Image

def extract_text_from_image(filepath: str) -> str:
    try:
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        return ""
