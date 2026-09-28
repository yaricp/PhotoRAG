## ADDED Requirements

### Requirement: Every photo launch path uses bounded shared admission

PhotoRAG SHALL admit photo runs through one persistent queue shared by watcher events, folder scans, manual full runs, retries, and recovery actions. The configured concurrency limit SHALL apply across event loops and worker processes, not only within one batch function.

#### Scenario: Many files arrive at once

- **WHEN** a watcher receives 24 new photos within a short interval while local Ollama is configured
- **THEN** PhotoRAG records each photo as queued or running
- **AND** it does not launch 24 unrestricted photo pipelines or concurrent local Ollama requests
- **AND** the Processing page exposes queued work and its progress

#### Scenario: The same photo is submitted twice

- **WHEN** two launch paths submit the same photo while a full run is queued or running
- **THEN** PhotoRAG does not create two active full runs for that photo

#### Scenario: A different provider is configured

- **WHEN** the pipeline uses built-in or cloud models rather than local Ollama
- **THEN** local Ollama's safety limit does not unnecessarily block unrelated model work

### Requirement: Pipeline run outcomes reflect actual task results

PhotoRAG SHALL track each photo run and its task attempts through all applicable phases. A run SHALL be completed successfully only when every required task succeeded or was legitimately inapplicable; a failed required task or missing required output SHALL produce a completed-with-errors outcome. A task without its prerequisite SHALL be marked skipped with a reason rather than done.

#### Scenario: Description fails but phase four executes

- **WHEN** description fails and a later phase has no document text to embed
- **THEN** the description is failed, dependent tasks are skipped with reasons, and the photo run is completed with errors
- **AND** a successful no-op phase-four task does not turn the run green

#### Scenario: Independent work succeeds

- **WHEN** description fails but metadata or another independent task succeeds
- **THEN** successful task outputs remain available and are shown as successful within the failed run

#### Scenario: All applicable work succeeds

- **WHEN** all required tasks complete and inapplicable tasks are explicitly skipped
- **THEN** the photo run is completed successfully with every applicable phase visible

### Requirement: Processing history is complete at photo-run granularity

PhotoRAG SHALL offer separate queued/in-progress and completed views. It SHALL paginate photo runs, not raw task rows, and SHALL allow a user to inspect all phases, attempts, outputs, and error reasons of each listed photo. Completed-with-errors runs SHALL remain visible and retryable.

#### Scenario: More than 50 task rows exist

- **WHEN** 24 photos create more than 50 task records
- **THEN** each photo remains discoverable in the appropriate view
- **AND** opening one photo shows its phase-zero through phase-four statuses regardless of task-row age

#### Scenario: User reruns one photo

- **WHEN** a new run is started for a previously failed photo
- **THEN** the new run is visible separately from the earlier attempt
- **AND** the earlier error evidence is not erased by recent-task pagination

### Requirement: Retry respects task dependencies

PhotoRAG SHALL let a user retry a failed task or explicitly rerun a whole photo. A task retry SHALL preserve independent successful outputs and schedule dependent skipped or stale tasks when the retried result makes them runnable.

#### Scenario: Description retry succeeds

- **WHEN** a user retries a failed description and it succeeds
- **THEN** translation and description-based embedding work that was skipped or made stale is offered or scheduled for retry
- **AND** already successful independent tags and categories are not discarded

#### Scenario: Retry fails again

- **WHEN** a retry still fails
- **THEN** its new error remains visible and the previous attempt remains inspectable

### Requirement: Interrupted work resumes only by user action

PhotoRAG SHALL preserve queued/running work as paused or interrupted when an application session ends and SHALL NOT automatically restart those photos on the next application launch. The user SHALL be able to resume selected work explicitly.

#### Scenario: App restarts after Ollama failure

- **WHEN** PhotoRAG restarts with unfinished photo runs from the previous session
- **THEN** those runs are visible as paused or interrupted
- **AND** no old photo is automatically reprocessed

#### Scenario: User chooses to resume

- **WHEN** a user selects interrupted photos and requests resume
- **THEN** they enter the same bounded queue as new work without losing prior task evidence

#### Scenario: A new photo arrives after restart

- **WHEN** a watcher detects a new photo after the application has restarted
- **THEN** that new photo may be queued normally without automatically resuming unrelated old photos
