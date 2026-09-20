# Remote API throttling and geocoding failure notes

## Context

When PhotoRAG processes many photos at once with remote models, every photo can trigger several independent remote calls:

- remote CLIP tagging;
- remote CLIP categorization;
- vision description;
- OCR or document detection;
- translation;
- embedding.

With a large batch this can create bursts of requests that exceed provider rate limits, especially OpenAI TPM/RPM limits. Current behavior lets tasks fail individually when the provider returns a rate-limit error.

## Future design: global remote API scheduler

Implement a single global scheduler/rate limiter for all remote model calls, shared across pipeline phases and workers.

Goals:

- Prevent too many concurrent requests to the same provider/model.
- Queue remote calls instead of letting all photo tasks hit the provider at once.
- Add provider-specific concurrency and rate settings.
- Retry transient rate-limit errors with exponential backoff and jitter.
- Preserve task visibility in the Processing page while queued/waiting.
- Avoid starving high-priority user actions such as chat.

Suggested structure:

```text
RemoteRequestScheduler
  provider: openai | anthropic | google_genai | deepl | ollama | ...
  model: gpt-4o-mini | text-embedding-3-small | ...
  task_kind: tags | categories | vision | ocr | translation | embedding | chat
  priority: interactive | pipeline | background
```

Suggested initial defaults:

- OpenAI remote pipeline calls: low concurrency, for example 1–2 simultaneous calls per model.
- Embeddings: separate bucket from chat/vision if provider limits differ.
- Chat: higher priority than background photo processing.
- Exponential backoff on `429` / rate-limit errors.
- Log queue wait time, retry count, and final provider error.

Possible implementation points:

- Wrap remote calls in `backend/src/model_services.py`.
- Do not duplicate rate-limit logic inside every task.
- Keep local model calls outside the remote scheduler.
- Make settings configurable later in the UI.

## User-facing behavior

If remote processing is throttled, the app should show that tasks are queued or waiting for provider rate limits, not failed immediately.

Example Processing page states:

```text
waiting for remote API slot
retrying after rate limit: 12s
queued behind 18 remote requests
```

## Geocoding failure note

Observed during Windows testing: geocoding can fail with a service unavailable error, and the string `Geocoding Service Unavailable` / `Geocoding service unavailable` may surface incorrectly in generated tags or metadata-derived text.

Known code path:

- `backend/src/geo.py::GeoEnricher.reverse_geocode()` catches `GeocoderTimedOut` and `GeocoderServiceError`.
- It currently returns a human-readable error string instead of returning `None` or a structured error.
- `metadata_task` stores `geo_result["address"]` when latitude/longitude exist.
- That error string can then be treated like a real address by downstream processing.

Future fix:

- Make geocoding failures structured, not address strings.
- Do not save `Geocoding Service Unavailable` as a photo address.
- Do not allow geocoding error strings to become tags, categories, or embedding text.
- Log the original geocoder exception with details so diagnostics explain whether it was timeout, service outage, network/DNS, rate limit, or blocked access.
- Consider retry/backoff and a per-run geocoding rate limit, because Nominatim usage policy is conservative.

Diagnostic commands for Windows testers:

```powershell
Select-String -Path "$env:APPDATA\PhotoRAG\photorag.log" -Pattern "Geo","GPS","Geocoding","Nominatim","clip/tags","auto_tag" -CaseSensitive:$false | Select-Object -Last 120
```

```powershell
Select-String -Path "$env:APPDATA\PhotoRAG\photorag.log" -Pattern "Geocoder","Service Unavailable","TimedOut","429","rate_limit","Rate limit" -CaseSensitive:$false | Select-Object -Last 120
```
