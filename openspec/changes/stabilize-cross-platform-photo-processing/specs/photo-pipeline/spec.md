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

### Requirement: Startup retry is opt-in and bounded

PhotoRAG SHALL provide a persisted Processing setting labeled `Retry unfinished tasks at startup`. It SHALL default to off for a new installation and remain off on upgrade unless the user explicitly enables it; an existing saved preference SHALL survive upgrades. When off, prior failed/interrupted tasks SHALL remain visible without automatic retry. When on, each application startup SHALL enqueue at most one new attempt for each eligible failed task and task interrupted while queued/running in a previous session, using the shared bounded queue. Successful tasks, explicitly paused work, and canceled work SHALL NOT be rerun. If an automatic attempt fails, it SHALL remain visible as failed and SHALL NOT retry again during the same application session. A later startup may retry it if the setting is still enabled.

#### Scenario: Startup retry is disabled

- **WHEN** PhotoRAG starts with the setting off and prior failed or interrupted work exists
- **THEN** the work remains visible and unchanged
- **AND** no prior task is automatically enqueued

#### Scenario: Startup retry is enabled

- **WHEN** PhotoRAG starts with the setting on and prior failed/interrupted tasks exist
- **THEN** one new attempt for each eligible task enters the shared bounded queue
- **AND** successful tasks, explicitly paused work, and canceled work are not rerun
- **AND** a task that fails again remains failed without an immediate retry loop

#### Scenario: The app restarts after a task failed

- **WHEN** an automatic attempt fails and the app later starts again with the setting still on
- **THEN** the failed task may receive one new attempt in that new session
- **AND** earlier attempts and successful independent outputs remain inspectable

#### Scenario: A new photo arrives after restart

- **WHEN** a watcher detects a new photo after the application has restarted
- **THEN** that photo enters the normal shared queue independently of any opted-in recovery work

### Requirement: Users can bulk-retry failed and incomplete tasks

The Processing page SHALL provide a one-click `Restart all failed and unfinished tasks` action. It SHALL enqueue currently eligible failed/interrupted tasks through the shared bounded queue, exclude tasks already queued/running, preserve attempt history and successful task outputs, and use dependency-aware retry behavior. It SHALL show queue progress and SHALL be unavailable when there are no eligible tasks.

#### Scenario: The user restarts all eligible work

- **WHEN** the user clicks `Restart all failed and unfinished tasks`
- **THEN** each eligible task is enqueued once through the shared queue
- **AND** no successful task or already active attempt is duplicated
- **AND** the Processing page shows the queued work and updated attempt counts

#### Scenario: A bulk retry recovers a prerequisite

- **WHEN** a failed prerequisite succeeds during a bulk retry
- **THEN** dependent skipped tasks that become runnable are scheduled according to the dependency policy
- **AND** independent successful outputs remain unchanged

### Requirement: Processing tabs count and group unique photos

PhotoRAG SHALL keep the in-progress and completed tab counts visible whether or not a tab is selected. Counts SHALL represent distinct photos, not pipeline runs or task attempts. A photo SHALL have at most one top-level card in the Processing view: while it has an active run it belongs to the in-progress tab; otherwise its latest settled outcome determines whether it belongs to the completed tab. The card SHALL show the number of attempts and provide access to their history.

#### Scenario: A task is retried several times

- **WHEN** the same photo has multiple completed or failed attempts
- **THEN** the Processing page shows one photo card and increments its attempt count
- **AND** its history still exposes every run, task state, and error
- **AND** the completed-tab count increases by one photo, not by the number of attempts

#### Scenario: A completed photo is being retried

- **WHEN** a new attempt for a photo is queued or running
- **THEN** that photo appears once in the in-progress tab
- **AND** it does not also appear as a second card in the completed tab
- **AND** prior attempts remain available from its history

### Requirement: Processing shows active work before queued work

The in-progress tab SHALL sort photos with currently executing work before photos waiting in the queue. Queued photos SHALL retain their queue order.

#### Scenario: A watcher submits a large batch

- **WHEN** one photo is being processed and other photos are queued
- **THEN** the currently executing photo appears at the top of the in-progress list
- **AND** queued photos appear after it in their expected queue order

### Requirement: Completed outputs are collapsed while phase status remains visible

Completed photo cards SHALL show phase/task states without hiding them behind the output disclosure. Detailed task results, including descriptions, tags, categories, and translations, SHALL be collapsed by default and expandable per photo.

#### Scenario: A user scans completed photos

- **WHEN** the completed tab is opened
- **THEN** each photo's green/red phase and task markers remain visible
- **AND** detailed generated results are initially collapsed
- **AND** the user can expand a photo to inspect its outputs

### Requirement: An active retry displays only its current attempt results

While a retry is queued or running, its photo card SHALL display the phase/task names and states for the active attempt only. Prior outputs SHALL NOT be presented as if they were produced by the active retry; prior attempts and outputs remain available in history.

#### Scenario: A failed tag task is retried

- **WHEN** tag retry starts for a photo that already has outputs from an earlier attempt
- **THEN** the in-progress card shows the retry's task names and live states without the prior tag results
- **AND** the earlier attempt and output remain inspectable in history

### Requirement: Model-generated tag writes are idempotent

PhotoRAG SHALL deduplicate normalized tag labels from a single model response before persisting them and SHALL save photo/tag associations idempotently across retries. Duplicate labels or already existing associations SHALL NOT cause the entire tag task to fail with a uniqueness error.

#### Scenario: The model returns the same tag more than once

- **WHEN** Ollama returns duplicate normalized labels for one photo
- **THEN** PhotoRAG persists one association per distinct tag using a deterministic confidence value
- **AND** the task completes without a unique-constraint error

#### Scenario: A retry returns a previously saved tag

- **WHEN** a retried tag task returns a tag already associated with the photo
- **THEN** PhotoRAG applies the documented idempotent update policy
- **AND** other valid tags from that response are still saved
