## ADDED Requirements

### Requirement: PhotoRAG checks the selected Ollama model's capabilities

PhotoRAG SHALL query the configured Ollama server for the user-selected model's available capabilities and native context limit before using it for a pipeline role. The same behavior SHALL apply on Windows, macOS, and Linux and SHALL NOT require a specific suggested model name.

#### Scenario: User selects a vision-capable model

- **WHEN** a user assigns an Ollama model that supports image input to description, OCR, or image-based tagging/categorization
- **THEN** PhotoRAG accepts that model and records its advertised context limit for automatic inference configuration

#### Scenario: User selects a text-only model for an image role

- **WHEN** the selected Ollama model does not support image input
- **THEN** PhotoRAG explains the incompatibility before the photo pipeline uses it
- **AND** it does not mark an image task complete without image analysis

#### Scenario: Model information is unavailable

- **WHEN** the configured Ollama server cannot provide reliable model metadata
- **THEN** PhotoRAG shows that compatibility/capacity is unverified
- **AND** it does not treat the model's advertised or assumed maximum context as a safe runtime default

### Requirement: Ollama context is chosen automatically for each configured model

PhotoRAG SHALL select a bounded context for Ollama inference using the task's input/output needs, the selected model's supported limit, and a conservative host-capacity policy. It SHALL pass the effective context with its own Ollama requests, display it as informational data, and SHALL NOT require users to enter token counts or change Ollama's global settings.

#### Scenario: Server-wide context is much larger than a photo request needs

- **WHEN** Ollama is configured globally for a 262,144-token context and PhotoRAG sends a one-photo request
- **THEN** PhotoRAG sends its automatically chosen bounded context for that request
- **AND** it leaves the Ollama server's global preference unchanged

#### Scenario: Another model is selected

- **WHEN** a user selects an Ollama model different from `qwen3-vl:2b-instruct`
- **THEN** PhotoRAG applies that model's capabilities, context limit, and host-capacity result instead of a Qwen-specific constant

#### Scenario: One model serves several pipeline roles

- **WHEN** the same Ollama model is used for description and image tagging or categorization
- **THEN** PhotoRAG uses a compatible, stable effective context for that processing workload without avoidable context-size switching between those tasks

#### Scenario: Hardware cannot support the needed context

- **WHEN** the model or host cannot run a context large enough for a photo request and its response
- **THEN** PhotoRAG reports a bounded, actionable incompatibility or resource error
- **AND** it does not spin indefinitely, silently truncate the image/prompt, or record a successful empty result

### Requirement: Ollama request failures remain visible and bounded

PhotoRAG SHALL limit simultaneous local Ollama inference requests on constrained hosts and record model, effective context, elapsed time, and error class for each failed pipeline call without storing image content or credentials in diagnostic logs.

#### Scenario: Ollama runner terminates during a bulk import

- **WHEN** Ollama returns a runner-terminated error, HTTP 500, or a timeout
- **THEN** the affected task finishes with a visible failure and the queue continues to other work within its configured limits

#### Scenario: Candidate list exceeds model context

- **WHEN** an image-tagging or categorization request exceeds the supported context because of its candidate list
- **THEN** PhotoRAG may retry with smaller candidate groups within a bounded policy
- **AND** any remaining failure is shown as failed rather than converted into zero tags or categories

#### Scenario: Standalone Ollama use

- **WHEN** the user runs Ollama outside PhotoRAG after configuring a model in PhotoRAG
- **THEN** PhotoRAG's per-request context choice has not changed Ollama's global context setting

### Requirement: Ollama OCR has a longer bounded deadline

PhotoRAG SHALL allow up to 300 seconds for an Ollama OCR request, including time waiting for the shared local inference gate. Other Ollama roles SHALL retain their existing deadline. OCR timeout failures SHALL remain visible and SHALL NOT be converted into empty successful results.

#### Scenario: A document needs longer than the standard inference budget

- **WHEN** the OCR task waits for the Ollama gate or reads a document for longer than the standard role deadline but completes within 300 seconds
- **THEN** PhotoRAG accepts the OCR result and records the actual duration

#### Scenario: OCR exceeds its dedicated deadline

- **WHEN** an Ollama OCR request does not finish within 300 seconds
- **THEN** the OCR task is marked failed with a timeout reason
- **AND** the shared gate is released so queued inference can proceed

### Requirement: Remote image tagging uses image-quality context

PhotoRAG SHALL provide measured blur and image-detail signals to remote vision-model tag/category prompts, instruct the model to avoid unsupported labels on blurry or low-detail images, and reject returned tag/category scores below 0.5. Scores SHALL be treated as model-reported ranking values rather than calibrated probabilities.

#### Scenario: Blurry or low-detail image is classified

- **WHEN** PhotoRAG sends a non-uniform image to a remote tag/category model
- **THEN** the prompt includes its blur and detail assessment
- **AND** labels with model-reported scores below 0.5 are not saved

#### Scenario: Model returns invalid JSON

- **WHEN** the remote tagger returns malformed or truncated JSON
- **THEN** PhotoRAG makes at most one format-only correction request
- **AND** if that response remains invalid, the task fails with a clear parse error
- **AND** timeouts and other provider errors are not retried automatically
