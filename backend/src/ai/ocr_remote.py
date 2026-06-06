import base64

from langchain_core.messages import HumanMessage
from loguru import logger

OCR_PROMPT = (
    "Extract all text visible in this image. "
    "Return only the extracted text, preserving line breaks. "
    "Return an empty string if no text is present."
)


def _encode_image_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class RemoteOCR:
    """Extract text from images using a remote vision-capable LLM."""

    def __init__(self, llm):
        self.llm = llm

    def extract_text(self, file_path: str) -> str:
        image_b64 = _encode_image_base64(file_path)
        msg = HumanMessage(
            content=[
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {"type": "text", "text": OCR_PROMPT},
            ]
        )
        try:
            response = self.llm.invoke([msg])
            return response.content.strip()
        except Exception as exc:
            logger.error(f"[RemoteOCR] LLM call failed: {exc}")
            return ""
