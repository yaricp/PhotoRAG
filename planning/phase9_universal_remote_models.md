# Phase 9 — Universal Remote Model Support + UI Loading States

**Goal:** Extend every AI pipeline stage (vision, CLIP tagger, translation, OCR) to work with
multiple local *and* remote providers, using the same architecture already established for
embedding and chat. Add meaningful loading-state UI to ModelsPage and ChatPage.

---

## Current State (baseline)

| Model type  | Local              | Remote (today)                | Target remote                              |
|-------------|--------------------|-------------------------------|--------------------------------------------|
| Embedding   | SentenceTransformer| LangChain (done ✓)            | —                                          |
| Chat        | HuggingFace pipe   | LangChain (done ✓)            | —                                          |
| Vision      | QwenVL via HF      | Raw HTTP POST (one custom URL)| OpenAI, Anthropic, Google, Ollama          |
| CLIP        | OpenCLIP           | Raw HTTP POST (one custom URL)| Vision-LLM-based tagger (all providers)   |
| Translation | HelsinkiNLP NLLB   | Raw HTTP POST (one custom URL)| OpenAI, Anthropic, Google, Ollama, DeepL  |
| OCR         | EasyOCR            | Raw HTTP POST (one custom URL)| OpenAI, Anthropic, Google, Ollama          |

---

## Design Principles

1. **Consistent provider abstraction** — each model type gets a `_build_langchain_*()` builder
   returning the right LangChain class; mirrors what `_build_langchain_embedder()` already does.
2. **TDD** — failing test first, minimum code to pass, refactor.
3. **No breaking changes to local paths** — queue workers and registry unchanged when mode=local.
4. **DB config as single source of truth** — `read_model_config_from_db()` already returns
   `mode`, `model_name`, `url`, `api_key`, `model_provider`. No new DB columns needed for P1–P4.
5. **Registry stays lazy-local** — the registry only loads local models. Remote calls bypass it
   entirely and go directly through LangChain inside `model_services.py`.

---

## Architecture for Each Model Type

### Vision & OCR (multimodal LLM pattern)
Both send **image + text prompt** to a vision-capable LLM and return plain text.
They share one builder:

```python
# model_services.py
def _build_langchain_vision_model(provider, model_name, api_key, api_url):
    """Return a LangChain chat model that accepts image content."""
    p = (provider or "").lower()
    if p == "ollama":   from langchain_ollama import ChatOllama;     return ChatOllama(...)
    if p == "anthropic": from langchain_anthropic import ChatAnthropic; return ChatAnthropic(...)
    if p in ("google_genai", "google"):
        from langchain_google_genai import ChatGoogleGenerativeAI;  return ChatGoogleGenerativeAI(...)
    # default → OpenAI-compatible
    from langchain_openai import ChatOpenAI;  return ChatOpenAI(...)

async def _call_remote_vision(cfg, file_path, prompt_text) -> str:
    image_b64 = _encode_image_base64(file_path)
    llm = _build_langchain_vision_model(...)
    msg = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        {"type": "text", "text": prompt_text},
    ])
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, llm.invoke, [msg])
    return response.content
```

OCR uses the same builder with a fixed prompt:
`"Extract all text visible in this image. Return only the extracted text, preserving line breaks. Return an empty string if no text is present."`

### CLIP / Remote Tagger (vision-LLM-as-classifier pattern)
CLIP does zero-shot classification against a large tag vocabulary. For remote providers:
- Pre-select the top-N candidate tags using a fast heuristic (or send a curated subset)
- Send **image + tag candidates** to a vision LLM
- Ask for structured JSON output: list of `{"tag": "...", "score": 0.xx}` pairs
- Match back against vocabulary; filter by threshold

```python
# ai/clip_remote.py
class RemoteClipTagger:
    def __init__(self, llm, tags: list[str], categories: list[str], threshold=0.5):
        ...
    def get_tags(self, file_path: str) -> list[tuple[str, float]]:
        # Sends image + top-200 tag candidates to LLM with structured prompt
        # Returns [(tag_name, score), ...]
    def get_categories(self, file_path: str) -> list[tuple[str, float]]:
        # Same for categories
```

This works identically for any vision-capable provider: OpenAI, Anthropic, Google, Ollama.

### Translation (LLM chat pattern + specialty services)
```python
# ai/translator_remote.py
class RemoteTranslator:
    def __init__(self, llm=None, provider=None, api_key=None, api_url=None):
        ...
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        # LangChain providers: format as ChatPromptTemplate → invoke → .content
        # deepl: POST https://api-free.deepl.com/v2/translate
        # libretranslate: POST {api_url}/translate
```

Supported providers: `openai`, `anthropic`, `google_genai`, `ollama`, `deepl`, `libretranslate`

---

## Work Items

### P0 — UI Loading States (est. 2h)

**Backend changes:**
- `/api/system/status/` already exists and reads `model_states` from DB.
- Extend it to also report whether the chat model is currently loaded in the registry:
  ```python
  # Check registry._chat_model is not None (no DB round-trip needed)
  from src.ai.registry import registry
  registry_chat_ready = registry._chat_model is not None
  ```
- Return a `"chat_ready": bool` field in the response.

**Frontend — ModelsPage:**
- Current: `if (loading) return <div className="models-page"><Spinner size="lg" /></div>`
- Change: Center the spinner with a descriptive message:
  ```tsx
  if (loading) return (
    <div className="models-page models-page--loading">
      <Spinner size="lg" />
      <p className="models-page__loading-text">Loading model configurations…</p>
    </div>
  )
  ```

**Frontend — ChatPage:**
- On mount: GET `/api/system/status/`; if `chat_ready === false`, show a dismissible banner:
  `"The AI chat model is still warming up. Your first message may take a moment."`
- Auto-dismiss when a successful chat response arrives.
- Poll every 5 s until ready (stop polling after first message sent or banner dismissed).

**Tests:**
- `test_main.py`: assert `/api/system/status/` returns `chat_ready` field
- `ChatPage.test.tsx`: mock status endpoint returning not-ready; assert banner renders

---

### P1 — Remote Vision (est. 3h)

**New code:**
- `backend/src/model_services.py`
  - `_encode_image_base64(file_path: str) -> str` — read file, base64 encode
  - `_build_langchain_vision_model(provider, model_name, api_key, api_url)` — builder
  - `_call_remote_vision(cfg, file_path, prompt_text) -> str` — dispatch
  - Update `call_vision_model()`: replace raw `_call_remote()` with `_call_remote_vision()`

**Queue changes:**
- `backend/src/queues/vision_queue.py`
  - `_get_model()`: if mode=remote → `logger.info("mode=remote — skipping local model load"); return None`
  - `call_local_vision_model()`: if model is None → save error result, return early

**Providers supported:**

| Provider        | LangChain class             | Notes                               |
|-----------------|-----------------------------|-------------------------------------|
| `openai`        | `ChatOpenAI`                | GPT-4o, gpt-4-vision-preview        |
| `anthropic`     | `ChatAnthropic`             | claude-3-haiku/sonnet/opus          |
| `google_genai`  | `ChatGoogleGenerativeAI`    | gemini-1.5-flash, gemini-1.5-pro    |
| `ollama`        | `ChatOllama`                | llava, bakllava, moondream          |

**Tests — `backend/tests/test_vision_remote.py`:**
```python
# TDD order:
# 1. test_encode_image_base64_returns_string
# 2. test_build_vision_model_openai
# 3. test_build_vision_model_anthropic
# 4. test_build_vision_model_google
# 5. test_build_vision_model_ollama
# 6. test_call_vision_model_remote_dispatches_correctly
# 7. test_call_vision_model_local_uses_huey
```

---

### P2 — Remote CLIP (est. 4h)

**New file: `backend/src/ai/clip_remote.py`**
```python
class RemoteClipTagger:
    """Vision-LLM-based zero-shot tagger. Drop-in replacement for ClipTagger (remote mode)."""
    
    TAGS_PROMPT = """
You are an image classification assistant.
Given the image and the candidate tag list below, return a JSON array of objects.
Each object: {"tag": "<tag_name>", "score": <float 0.0-1.0>}.
Include only tags that clearly describe visible content. Minimum score: 0.3.
Candidate tags: {tags}
Return ONLY the JSON array, no other text.
"""
    
    def __init__(self, llm, all_tags: list[str], all_categories: list[str], threshold: float = 0.3):
        self.llm = llm
        self.all_tags = all_tags
        self.all_categories = all_categories
        self.threshold = threshold
        
    def _classify(self, file_path: str, candidates: list[str]) -> list[tuple[str, float]]:
        # Encode image, format prompt, call LLM, parse JSON response
        ...
    
    def get_tags(self, file_path: str) -> list[tuple[str, float]]:
        # Pass all_tags (up to 200, chunked if needed)
        return self._classify(file_path, self.all_tags[:200])
    
    def get_categories(self, file_path: str) -> list[tuple[str, float]]:
        return self._classify(file_path, self.all_categories)
    
    def encode_image(self, file_path: str) -> list[float]:
        # Not supported in remote mode — raise NotImplementedError or return []
        raise NotImplementedError("Image encoding not available in remote CLIP mode")
```

**`model_services.py` changes:**
- `_call_remote_clip(cfg, file_path, task)` — instantiates `RemoteClipTagger`, delegates

**`clip_queue.py` changes:**
- `_get_model()`: check mode from DB; if remote → return None
- `call_local_clip_model()`: if model is None → save error, return early

**`registry.py` changes:**
- `clip_tagger` property: check DB config mode; if remote → return `RemoteClipTagger` instance
  (lazy-loaded like all other models, but skips OpenCLIP loading)

**Tests — `backend/tests/test_clip_remote.py`:**
```python
# TDD order:
# 1. test_remote_clip_tagger_get_tags_returns_scored_list
# 2. test_remote_clip_tagger_parses_llm_json_response
# 3. test_remote_clip_tagger_filters_by_threshold
# 4. test_remote_clip_tagger_get_categories
# 5. test_call_clip_model_remote_dispatches
# 6. test_call_clip_model_local_uses_huey
```

---

### P3 — Remote Translation (est. 3h)

**New file: `backend/src/ai/translator_remote.py`**
```python
class RemoteTranslator:
    TRANSLATION_PROMPT = (
        "Translate the following text to {target_lang}. "
        "Return ONLY the translated text, nothing else.\n\n{text}"
    )
    
    def __init__(self, provider, model_name, api_key=None, api_url=None,
                 src_lang="Russian", tgt_lang="English"):
        self.provider = provider
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self._llm = None      # lazy
        ...
    
    def translate(self, text: str, backward: bool = False) -> str:
        if self.provider == "deepl":
            return self._translate_deepl(text, backward)
        if self.provider == "libretranslate":
            return self._translate_libretranslate(text, backward)
        return self._translate_llm(text, backward)
    
    def _translate_llm(self, text: str, backward: bool) -> str:
        # Builds prompt, calls LangChain chat model, returns .content
    
    def _translate_deepl(self, text: str, backward: bool) -> str:
        # POST https://api-free.deepl.com/v2/translate (or api.deepl.com for Pro)
    
    def _translate_libretranslate(self, text: str, backward: bool) -> str:
        # POST {api_url}/translate
```

**`model_services.py` changes:**
- `_call_remote_translation(cfg, text, backward)` — instantiates `RemoteTranslator`, delegates
- Update `call_translation_model()`: replace raw `_call_remote()` with `_call_remote_translation()`

**`translation_queue.py` changes:**
- `_get_model()`: if mode=remote → return None (skip NLLB download)

**`registry.py` changes:**
- `translator` property: check DB config mode; if remote → return `RemoteTranslator` instance

**Providers supported:**

| Provider          | Backend                  | API key required  |
|-------------------|--------------------------|-------------------|
| `openai`          | ChatOpenAI               | Yes               |
| `anthropic`       | ChatAnthropic            | Yes               |
| `google_genai`    | ChatGoogleGenerativeAI   | Yes               |
| `ollama`          | ChatOllama               | No                |
| `deepl`           | requests (direct HTTP)   | Yes               |
| `libretranslate`  | requests (direct HTTP)   | Optional          |

**Tests — `backend/tests/test_translation_remote.py`:**
```python
# TDD order:
# 1. test_remote_translator_llm_path_calls_langchain
# 2. test_remote_translator_deepl_path_posts_to_api
# 3. test_remote_translator_libretranslate_path
# 4. test_remote_translator_backward_flag_swaps_direction
# 5. test_call_translation_model_remote_dispatches
# 6. test_call_translation_model_local_uses_huey
```

---

### P4 — Remote OCR (est. 2h)

**New file: `backend/src/ai/ocr_remote.py`**
```python
OCR_PROMPT = (
    "Extract all text visible in this image. "
    "Return only the extracted text, preserving line breaks. "
    "Return an empty string if no text is present."
)

class RemoteOCR:
    def __init__(self, llm):
        self.llm = llm
    
    def extract_text(self, file_path: str) -> str:
        image_b64 = _encode_image_base64(file_path)
        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            {"type": "text", "text": OCR_PROMPT},
        ])
        response = self.llm.invoke([msg])
        return response.content.strip()
```

Reuses `_build_langchain_vision_model()` from P1 — same providers: openai, anthropic, google_genai, ollama.

**`model_services.py` changes:**
- `_call_remote_ocr(cfg, file_path) -> str` — instantiates `RemoteOCR`, delegates
- Update `call_ocr_model()`: replace raw `_call_remote()` with `_call_remote_ocr()`

**`ocr_queue.py` changes:**
- `_get_model()`: if mode=remote → return None (skip EasyOCR download)

**Tests — `backend/tests/test_ocr_remote.py`:**
```python
# TDD order:
# 1. test_remote_ocr_sends_image_and_prompt_to_llm
# 2. test_remote_ocr_returns_content_from_response
# 3. test_remote_ocr_returns_empty_string_on_no_text
# 4. test_call_ocr_model_remote_dispatches
# 5. test_call_ocr_model_local_uses_huey
```

---

### P5 — ModelsPage Provider UI (est. 2h)

Extend the provider dropdown to all model types when mode=remote.

**Provider options per model type:**

| Model type    | Providers (remote)                                                    |
|---------------|-----------------------------------------------------------------------|
| `vision`      | openai, anthropic, google_genai, ollama                               |
| `clip`        | openai (vision-LLM), anthropic, google_genai, ollama                  |
| `translator`  | openai, anthropic, google_genai, ollama, deepl, libretranslate        |
| `ocr`         | openai, anthropic, google_genai, ollama                               |
| `embedding`   | openai, google_genai, ollama *(already done)*                         |
| `chat`        | openai, anthropic, google_genai, google_vertexai, ollama, groq, etc.  *(done)* |

**ModelsPage.tsx changes:**
- Extract provider dropdown into a `<ProviderSelect>` component
- Render it for ALL types when mode=remote (not just chat/embedding as today)
- Add provider-specific hint text (e.g., Ollama URL, DeepL API key note)
- Show appropriate model name placeholder per provider

**Example placeholders:**
```
vision + openai  → "gpt-4o"
vision + ollama  → "llava"
translator + deepl → "deepl" (model name not needed, just API key)
ocr + anthropic  → "claude-3-haiku-20240307"
```

---

## Testing Strategy (TDD sequence per phase)

For each phase:
1. **Write test file** with all planned tests (all failing).
2. **Add new file(s)** (`clip_remote.py`, `translator_remote.py`, etc.) with stub classes.
3. **Make tests pass** one by one, implementing actual logic.
4. **Update `model_services.py`** to wire the new paths; update the relevant test in `test_model_services.py`.
5. **Update UI** (`ModelsPage.tsx`); verify manually.

Test isolation strategy (mirrors existing patterns):
- Mock LangChain classes at the class level using `unittest.mock.patch`
- Mock `read_model_config_from_db` to control mode/provider
- Never perform actual network calls in tests
- Frontend tests: mock `fetch` / API client module

---

## Dependencies

All LangChain providers already added in `pyproject.toml` from Phase 8:
- `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`, `langchain-ollama`

New optional dependencies (only needed if user selects these providers):
- `deepl` → `uv pip install deepl` (for DeepL provider)
- No new deps for libretranslate (plain HTTP)

These are NOT added to `pyproject.toml` as required deps — they're documented
as optional and the code raises a clear `ImportError` with install instructions
if the package is missing (same pattern as chat model providers).

---

## Execution Order

```
P0  UI Loading States    (no model code changes; quick wins)
P1  Remote Vision        (establishes shared image-encoding + vision-builder helpers)
P4  Remote OCR           (reuses P1 helpers; small delta)
P3  Remote Translation   (independent; simpler because text-only)
P2  Remote CLIP          (most complex; builds on P1 image-encoding)
P5  ModelsPage UI        (UI catch-up after all backends are done)
```

P1 before P4 because `_build_langchain_vision_model` and `_encode_image_base64` are shared.
P2 last among backend tasks because it's the most novel (structured LLM output, chunking).

---

## Open Questions (to clarify with user before starting)

1. **CLIP remote tag chunking**: The full OpenImages tag vocabulary has ~600 entries.
   Should we send all ~600 tags per image call (higher cost, single round-trip),
   or chunk into groups of 100–200 (lower cost per call, multiple round-trips)?
   *Proposed default: send top-200 most common tags + all categories in one call.*

2. **Translation direction**: The current translator uses `DEFAULT_LANGUAGE` from settings
   to determine forward/backward. For remote providers, do you want to keep the same
   forward=any→DEFAULT_LANGUAGE / backward=any→English convention, or expose
   explicit source/target language selectors in the UI?
   *Proposed: keep existing convention for now.*

3. **CLIP remote model fallback**: If the vision LLM returns malformed JSON for tag scores,
   should we fall back to local CLIP, return empty, or surface the error to the pipeline?
   *Proposed: log warning + return empty list (photo gets no tags from this pass).*

4. **System status polling interval**: ChatPage banner polls every 5 s.
   Is this acceptable, or should it be WebSocket-based for instant updates?
   *Proposed: polling (simpler, consistent with existing architecture).*
