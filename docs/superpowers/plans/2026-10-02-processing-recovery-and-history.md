# Processing Recovery and History Implementation Plan

## Goal

Implement the active OpenSpec change `stabilize-cross-platform-photo-processing` in small, test-driven slices. Processing history is grouped by photo, queue work remains bounded, startup recovery is opt-in, and prior successful outputs and task evidence remain intact.

## Constraints

- Follow red → green → refactor for every behavior: add a focused test, run it and confirm the expected failure, implement the smallest change, rerun the test, then run nearby regression tests.
- Use the existing persistent shared queue for every new retry path. Do not create a parallel worker or unbounded task fan-out.
- Preserve successful outputs, explicit pauses/cancellations, and prior task attempts. Never automatically retry the same failure repeatedly during one app session.
- Update OpenSpec checkboxes only after the corresponding behavior and checks pass.

## Steps

1. **Idempotent tag persistence**
   - Add database-backed tests for duplicate model labels in one result and associations that already exist from a prior attempt.
   - Confirm the current implementation fails on the duplicate association; deduplicate normalized labels and make persistence idempotent while preserving deterministic scores.
   - Validate the focused CLIP/tag tests and existing tag confidence tests.

2. **Task eligibility and grouped run API**
   - Add tests for selecting failed/interrupted tasks while excluding successful, paused, and canceled tasks; include dependency-aware retries and bounded single-photo admission.
   - Extend the queue intent/migration safely for a selected set of task names, then execute each eligible task once in dependency order within one admitted run.
   - Add API tests for distinct-photo pagination, attempt counts/history, latest active attempt taking precedence, and active-before-queued ordering.

3. **Opt-in startup recovery and bulk retry**
   - Add tests proving the persisted setting defaults off, survives restart, and only enqueues eligible work when enabled.
   - Add backend tests for one-click bulk retry across photos, deduplication against active queue entries, preservation of completed outputs, and no same-session retry loop.
   - Implement the setting and bulk endpoint through the same queue admission and concurrency controls.

4. **Processing UI behavior**
   - Update component tests first for always-visible photo counts, grouped cards with attempt history, active-first ordering, collapsed completed outputs, and hiding stale outputs during active retries.
   - Add tests for the default-off startup preference, bulk retry action, queued progress, and disabled state when nothing is eligible.
   - Implement and localize the UI in English, Russian, and Spanish; keep phase/task state markers visible.

5. **Validation and OpenSpec completion**
   - Run focused backend and frontend tests after each slice, then project checks and strict OpenSpec validation.
   - Exercise queue restart/recovery behavior and review the final diff for output/history preservation and cross-platform assumptions.
   - Mark only verified OpenSpec tasks complete and commit the implementation separately from the already committed specification update.

## Progress

- Step 1 is implemented. The local macOS log shows duplicate candidate labels causing `UNIQUE constraint failed: photo_tags.photo_id, photo_tags.tag_id`; the data layer now normalizes/deduplicates each response and serializes association writes. A separate later Ollama retry for photo 7 hit its request timeout at about 115 seconds and remains an explicit failed attempt, not a hung task.
- Step 2 is implemented and covered for latest outcomes, dependency-skipped tasks, 24-photo retry admission, one active local-Ollama claim, grouped attempt history, distinct-photo counts, and running-before-queued ordering.
- Step 3 is implemented with default-off persisted startup retry and a Processing bulk action. A repeated admission during the same active session queues zero additional work.
- Step 4 is implemented and component-tested, including task names by phase while a retry is queued before the worker creates task rows.
- Step 5 remains: strict OpenSpec validation and focused recovery/API/tag checks pass (106 tests), and the five pre.7 installers are built and checksum-verified. Full backend collection still leaks `MagicMock` modules from legacy test files; real target-OS inference and upgrade runs remain outstanding. Keep those OpenSpec checks open until the suite and hardware evidence are resolved.
