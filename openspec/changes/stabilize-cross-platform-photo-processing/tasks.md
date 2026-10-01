## 1. Persistent run records and truthful task states

- [x] 1.1 Add a migration-safe photo-run/attempt data model; preserve existing photos, outputs, configurations, task evidence, venv, and downloaded Ollama models.
- [x] 1.2 Aggregate task outcomes into queued, running, completed, completed-with-errors, paused, and interrupted run states; record skipped tasks and prerequisite reasons instead of green no-op success.
- [x] 1.3 Replace unconditional pipeline-success reporting with a final summary of required outputs, failed tasks, and skipped dependencies; add focused tests for partial phase-1 failure and phase-4 no-op behavior.
- [x] 1.4 Make task retry dependency-aware so a recovered description can trigger missing translation/embedding without clearing successful independent results; preserve prior attempts.

## 2. Model-agnostic Ollama inference policy

- [x] 2.1 Query `/api/show` for any user-selected Ollama model, verify image capability for image roles, and read its native context limit with explicit unknown-metadata handling.
- [x] 2.2 Implement automatic model/role/host-aware context selection and pass `num_ctx` with PhotoRAG Ollama requests; never write Ollama global settings or require a manual token field.
- [x] 2.3 Keep effective context stable for one Ollama model across the photo-processing workload; display the chosen value and its reason read-only.
- [x] 2.4 Bound local Ollama inference concurrency and duration; propagate runner termination, memory, timeout and context errors without successful empty results or silent image truncation.
- [ ] 2.5 Verify context decisions with mocked small-context, non-vision, unavailable-metadata, shared-role, remote-host and 262,144-token-global-setting cases; calibrate safe budgets on target hardware.

## 3. Shared queue and explicit recovery

- [x] 3.1 Route watcher, folder scan, manual run, agent-tool run, and retry submissions through one persistent admission queue with transactional claims and duplicate-active-run protection across threads/processes.
- [x] 3.2 Apply a conservative local-Ollama photo-run limit across all launch paths, without unnecessarily blocking unrelated native/cloud work; expose queue position and waiting time.
- [ ] 3.3 Replace startup auto-rerun/deletion of unfinished task rows with paused/interrupted records and an explicit resume action for selected photos.
- [ ] 3.4 Test a 24-file watcher burst, simultaneous launch paths, cancellation/restart, user-selected resume, and new watcher events after restart.

## 4. Processing and status UI

- [ ] 4.1 Add paginated photo-run APIs and Processing tabs for queued/in-progress and completed work; show all phases, actual outputs, attempts, errors, and retry/full-rerun actions.
- [ ] 4.2 Confirm a completed photo remains discoverable after more than 50 task rows and that a rerun does not hide the earlier failed attempt.
- [ ] 4.3 Add `updated_at` to the watcher API with defined timezone semantics; format it safely and localize the unknown value and status label.
- [ ] 4.4 Refresh the pipeline-warning banner after model saves and availability changes; distinguish missing configuration from temporary unavailability and localize English/Russian/Spanish copy.
- [ ] 4.5 Verify the Ollama model download/inventory workflow still reuses installed models and remains usable while processing is queued.

## 5. Cross-platform validation and release candidates

- [ ] 5.1 Run focused backend migration/queue/inference/retry tests and frontend pagination/date/banner tests; run existing project checks and `openspec validate`.
- [ ] 5.2 Exercise the `verification.md` 24-photo scenario on the 16 GiB macOS test host, checking database outputs, Ollama runner stability, effective context, queue limits and complete UI history.
- [ ] 5.3 Exercise the same model/configuration and failure/retry paths on Windows x64 with 8 GiB RAM and a Linux host; record limitations as explicit errors rather than hangs or false success.
- [ ] 5.4 Verify a lower-context Ollama model, a text-only model selected for an image role, the same model assigned to several functions, an unavailable Ollama server, and a custom Ollama URL.
- [ ] 5.5 Build macOS universal, Windows x64/ARM64 and Linux x64/ARM64 candidates from the same source revision; inspect bundled backend/frontend and smoke-test real packaged installs where hardware is available.
- [ ] 5.6 Confirm upgrading a previous test install does not repull models, reinstall the Python environment, erase photos, or silently resume interrupted work; record candidate versions and checksums before release decisions.
