## ADDED Requirements

### Requirement: Ollama is a distinct user-facing local processing choice

PhotoRAG SHALL offer a third processing choice for local Ollama in the setup wizard and Models page. It SHALL persist this choice using the existing Ollama provider configuration without an API key and SHALL require the user to select or enter a model name.

#### Scenario: Selecting Ollama during setup

- **WHEN** a user selects local Ollama for a task on any supported desktop platform
- **THEN** the provider becomes Ollama, the URL defaults to localhost, and no model is silently chosen or API key requested

#### Scenario: Existing Ollama configuration

- **WHEN** a saved Ollama configuration is opened
- **THEN** the third local Ollama processing choice is shown as selected with its saved model name

### Requirement: Chosen Ollama models download inside PhotoRAG

PhotoRAG SHALL check the local Ollama server for the model explicitly chosen by the user, download it when absent, show progress and completion, and surface a retryable error when Ollama or the download is unavailable. It SHALL support this workflow in the first-run wizard and later model configuration on Windows, macOS and Linux.

#### Scenario: Chosen model is absent

- **WHEN** a user continues setup or saves an Ollama model configuration and the chosen model is absent
- **THEN** PhotoRAG starts an Ollama download in the background and displays its progress before proceeding

#### Scenario: Model is already installed

- **WHEN** the chosen model is already listed by Ollama
- **THEN** PhotoRAG reuses it without another download

#### Scenario: Several tasks use the same model

- **WHEN** multiple setup tasks choose the same Ollama model and server URL
- **THEN** PhotoRAG downloads it at most once

#### Scenario: Configuring several tasks on the Models page

- **WHEN** a user saves an Ollama model for one task and continues configuring another task
- **THEN** the Models page remains usable, shows download progress within the affected task card, and shares an in-progress pull for the same model and local server

#### Scenario: Saving an already installed model on the Models page

- **WHEN** the chosen Ollama model is already installed
- **THEN** PhotoRAG saves the task configuration without showing a download modal or starting a pull

#### Scenario: Pull fails or Ollama is missing

- **WHEN** Ollama cannot be reached or a pull fails
- **THEN** PhotoRAG shows the error and lets the user return to configuration or retry without claiming completion

### Requirement: Installed Ollama models and disk space are manageable

PhotoRAG SHALL provide an Ollama model-management page listing locally installed model names and sizes, the free space on the model disk when determinable, and a low-space warning. It SHALL allow user-initiated deletion of one or all installed models with confirmation.

#### Scenario: Experimenting with another model

- **WHEN** a user enters a model name on the Ollama models page and requests a download
- **THEN** PhotoRAG downloads that named model with progress and refreshes the installed-model list

#### Scenario: Reviewing installed models

- **WHEN** a user opens the Ollama models page
- **THEN** each model and its reported size are shown alongside the model storage location and available disk space, or a clear unknown/estimated status

#### Scenario: Disk space is low

- **WHEN** the model disk has less than 5 GiB free or less than 10% of its capacity free
- **THEN** PhotoRAG suggests deleting unused models without deleting any automatically

#### Scenario: Deleting one model

- **WHEN** a user confirms deletion of one installed model
- **THEN** PhotoRAG asks Ollama to delete that model and refreshes the list and disk space

#### Scenario: Deleting all models

- **WHEN** a user confirms deletion of all installed models
- **THEN** PhotoRAG asks Ollama to delete each model and refreshes the list and disk space

#### Scenario: A model is used by PhotoRAG

- **WHEN** a model selected for a PhotoRAG task is about to be deleted
- **THEN** the confirmation identifies the affected task; the model is not deleted without user confirmation

### Requirement: Ollama setup help is contextual and localized

PhotoRAG SHALL show the Ollama help article inside a closable modal from the wizard and Models page, in the current interface language and without either navigation sidebar. The article SHALL explain automatic model downloads, give a task-to-model recommendation table, and keep terminal commands in a separate optional section.

#### Scenario: User opens help before setup is complete

- **WHEN** a user opens Ollama help from the first-run wizard
- **THEN** the modal shows the current wizard language and closing it returns to the same setup state

#### Scenario: User chooses to use the terminal

- **WHEN** a user reads the optional manual section
- **THEN** commands for listing, pulling and removing Ollama models are available

#### Scenario: Limited disk space for a vision model

- **WHEN** a user reviews vision, OCR or image-tagging suggestions
- **THEN** a vision-capable Ollama model whose catalog size is under 2.5 GB appears as a suggestion, and the help article states its approximate size without selecting or downloading it automatically

#### Scenario: Reusing the compact model for text tasks

- **WHEN** a user with limited disk space reviews Ollama suggestions for chat or translation
- **THEN** the same compact model is available as an optional suggestion, while the help article explains that agent-tool and translation quality must be checked on the user's data

#### Scenario: Finding a suggested model after selecting Ollama

- **WHEN** a user selects Ollama for OCR or chat in the wizard or Models page
- **THEN** the model field and compact-model suggestion appear after the provider choice, so the user can select it without searching above the changed control

### Requirement: Windows messaging distinguishes built-in and Ollama models

PhotoRAG SHALL state that built-in local models are unavailable in the Windows build while separately installed Ollama models are available.

#### Scenario: Windows first-run configuration

- **WHEN** the setup wizard runs on Windows
- **THEN** it offers local Ollama and displays the distinction between built-in and Ollama models

### Requirement: Remote CLIP failures are visible and context overflow is retried

PhotoRAG SHALL mark remote image-tagging and categorization tasks as failed when the model call fails or returns an invalid response. An empty but valid result SHALL remain successful. When a provider rejects a candidate list for exceeding its context window, PhotoRAG SHALL retry with smaller candidate groups before reporting failure.

#### Scenario: Model rejects an oversized candidate list

- **WHEN** Ollama reports that a remote CLIP prompt exceeds its context window
- **THEN** PhotoRAG divides the candidate list and retries the smaller groups without losing their accepted tags or categories

#### Scenario: Model call or response is invalid

- **WHEN** a remote CLIP model call fails or returns malformed JSON
- **THEN** the corresponding pipeline task is marked failed with the error, rather than shown as complete with zero results
