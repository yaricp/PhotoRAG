"""
Remote CLIP tagger.

Uses a vision-capable LLM to classify images against a tag/category vocabulary,
replacing the local OpenCLIP zero-shot model when mode=remote.

Design:
- Sends image + up to 200 candidate tag names in one LLM call.
- Asks the LLM for JSON: [{"tag": "...", "score": 0.0-1.0}, ...]
- Filters results by threshold and validates against the known vocabulary.
- Returns [] on malformed JSON (logs a warning, pipeline continues without tags).
"""
import base64
import json
from loguru import logger
from langchain_core.messages import HumanMessage

MAX_TAGS_PER_CALL = 200

_CLASSIFY_PROMPT = """You are an image tagging assistant.
Given the image and the candidate tag list below, return a JSON array of objects.
Each object must have exactly two keys: "tag" (string) and "score" (float 0.0-1.0).
Include ONLY tags that clearly describe visible content in the image. Minimum score: {threshold}.
Do NOT invent tags that are not in the candidate list.
Return ONLY the JSON array — no explanation, no markdown fences.

Candidate tags:
{tags}"""


def _encode_image_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class RemoteClipTagger:
    """Drop-in tag/category classifier backed by a vision LLM instead of OpenCLIP."""

    def __init__(
        self,
        llm,
        all_tags: list[str],
        all_categories: list[str],
        threshold: float = 0.3,
    ):
        self.llm = llm
        self.all_tags = all_tags
        self.all_categories = all_categories
        self.threshold = threshold

    # ------------------------------------------------------------------
    # Public interface (mirrors ClipTagger)
    # ------------------------------------------------------------------

    def get_tags(self, file_path: str) -> list[tuple[str, float]]:
        candidates = self.all_tags[:MAX_TAGS_PER_CALL]
        return self._classify(file_path, candidates, self.all_tags)

    def get_categories(self, file_path: str) -> list[tuple[str, float]]:
        return self._classify(file_path, self.all_categories, self.all_categories)

    def encode_image(self, file_path: str) -> list[float]:
        raise NotImplementedError(
            "Image embedding is not available in remote CLIP mode. "
            "Switch to a local CLIP model for encode_image support."
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify(
        self,
        file_path: str,
        candidates: list[str],
        valid_vocab: list[str],
    ) -> list[tuple[str, float]]:
        if not candidates:
            return []

        image_b64 = _encode_image_base64(file_path)
        prompt = _CLASSIFY_PROMPT.format(
            threshold=self.threshold,
            tags=", ".join(candidates),
        )
        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            {"type": "text", "text": prompt},
        ])

        try:
            response = self.llm.invoke([msg])
            raw = response.content.strip()
            # Strip markdown fences if the model returns them anyway
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(f"[RemoteClipTagger] Malformed JSON from LLM: {exc} — returning []")
            return []
        except Exception as exc:
            logger.error(f"[RemoteClipTagger] LLM call failed: {exc}")
            return []

        if not isinstance(items, list):
            logger.warning("[RemoteClipTagger] Unexpected LLM response structure — returning []")
            return []

        vocab_set = set(valid_vocab)
        results = []
        for item in items:
            try:
                tag = item["tag"]
                score = float(item["score"])
            except (KeyError, TypeError, ValueError):
                continue
            if tag not in vocab_set:
                continue
            if score < self.threshold:
                continue
            results.append((tag, score))

        return results
