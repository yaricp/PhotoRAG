from src.ai.ocr import extract_text_from_image

def test_ocr_extraction_graceful_fail_without_binary():
    # If tesseract GUI binary isn't natively there, or the image doesn't exist, it should return "" instead of crashing
    text = extract_text_from_image("missing_file.jpg")
    assert text == ""
