"""
Remote CLIP tagger.

Uses a vision-capable LLM to classify images against a tag/category vocabulary,
replacing the local OpenCLIP zero-shot model when mode=remote.

Design:
- Sends image + up to 200 candidate tag names, splitting the list if the
  provider's context window is too small.
- Asks the LLM for JSON: [{"tag": "...", "score": 0.0-1.0}, ...]
- Filters results by threshold and validates against the known vocabulary.
- Propagates provider and invalid-response errors so the pipeline marks the task failed.
"""

import base64
import json
import math

from langchain_core.messages import HumanMessage
from loguru import logger

MAX_TAGS_PER_CALL = 200
REMOTE_CLIP_MIN_SCORE = 0.5

_CLASSIFY_PROMPT = """You are an image tagging assistant.
Given the image and the candidate tag list below, return a JSON array of objects.
Each object must have exactly two keys: "tag" (string) and "score" (float 0.0-1.0).
Include ONLY tags that clearly describe visible content in the image. Minimum score: {threshold}.
Do NOT invent tags that are not in the candidate list.
Image quality measured independently: {quality_context}.
If the image is blurry or has low detail, avoid labels whose visual evidence is uncertain. Scores are ranking estimates, not calibrated probabilities.
Return ONLY the JSON array — no explanation, no markdown fences.

Candidate tags:
{tags}"""

_JSON_REPAIR_PROMPT = """Correct only the JSON syntax in the text below.
Return exactly one valid JSON array of objects, preserving only tag names and numeric scores already present.
Do not add, remove, or change any tag or score except where required to repair syntax.
Return only the JSON array, with no markdown fences or explanation.

Text to repair:
{raw}"""


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
        threshold: float = REMOTE_CLIP_MIN_SCORE,
        image_quality: dict | None = None,
    ):
        self.llm = llm
        self.all_tags = all_tags
        self.all_categories = all_categories
        self.threshold = threshold
        self.image_quality = image_quality or {}

    # ------------------------------------------------------------------
    # Public interface (mirrors ClipTagger)
    # ------------------------------------------------------------------

    def get_tags(self, file_path: str) -> list[tuple[str, float]]:
        results = []
        for start in range(0, len(self.all_tags), MAX_TAGS_PER_CALL):
            results.extend(self._classify(file_path, self.all_tags[start : start + MAX_TAGS_PER_CALL], self.all_tags))
        return results

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
            quality_context=self._format_quality_context(),
            tags=", ".join(candidates),
        )
        msg = HumanMessage(
            content=[
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]
        )

        try:
            response = self.llm.invoke([msg])
            items = self._parse_response(response.content)
        except Exception as exc:
            message = str(exc).lower()
            if len(candidates) > 1 and "context" in message and ("exceed" in message or "too long" in message):
                middle = len(candidates) // 2
                logger.warning(
                    f"[RemoteClipTagger] Context too small; retrying in groups of {middle} and {len(candidates) - middle}"
                )
                return self._classify(file_path, candidates[:middle], valid_vocab) + self._classify(
                    file_path, candidates[middle:], valid_vocab
                )
            logger.error("[RemoteClipTagger] LLM call failed: {}", type(exc).__name__)
            raise

        if not isinstance(items, list):
            raise ValueError("[RemoteClipTagger] Expected a JSON array from the vision model")

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
            if not math.isfinite(score) or not 0.0 <= score <= 1.0 or score < self.threshold:
                continue
            results.append((tag, score))

        return results

    def _format_quality_context(self) -> str:
        metrics = self.image_quality
        if not metrics:
            return "blurred=unknown; low_detail=unknown; uniform=unknown"

        def flag(key: str) -> str:
            return "unknown" if key not in metrics else str(bool(metrics[key])).lower()

        return (
            f"blurred={flag('is_blurry')}; "
            f"low_detail={flag('is_low_detail')}; "
            f"uniform={flag('is_uniform')}; "
            f"blur_variance={metrics.get('blur_variance', 'unknown')}; "
            f"edge_density={metrics.get('edge_density', 'unknown')}; "
            f"entropy={metrics.get('entropy', 'unknown')}"
        )

    def _parse_response(self, raw: str):
        def parse(text: str):
            text = text.strip()
            if text.startswith("```"):
                text = text[3:]
                if text.startswith("json"):
                    text = text[4:]
                text = text.removesuffix("```").strip()
            return json.loads(text)

        try:
            items = parse(raw)
        except json.JSONDecodeError:
            try:
                corrected = self.llm.invoke([HumanMessage(content=_JSON_REPAIR_PROMPT.format(raw=raw[:12000]))])
            except Exception:
                raise
            try:
                items = parse(corrected.content)
            except (json.JSONDecodeError, AttributeError, TypeError) as repair_error:
                raise ValueError(
                    "[RemoteClipTagger] Model returned malformed JSON after one repair attempt"
                ) from repair_error
        if not isinstance(items, list):
            raise ValueError("[RemoteClipTagger] Expected a JSON array from the vision model")
        return items
