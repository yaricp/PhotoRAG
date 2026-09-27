# model-configuration Specification Delta

## ADDED Requirements

### Requirement: Local Ollama must be presented as a local model path

The desktop UI SHALL present an Ollama server running at localhost as a local model path, distinct from built-in local model downloads and cloud API providers.

#### Scenario: User configures Ollama on the Models page

- **WHEN** a user selects Ollama for a model capability
- **THEN** the UI labels the option as local via Ollama or equivalent wording
- **AND** it explains that Ollama runs on the user's computer when using `http://localhost:11434`
- **AND** it does not describe that configuration as a cloud provider

#### Scenario: User configures Ollama in the Setup Wizard

- **WHEN** a user selects Ollama during first-run model configuration
- **THEN** the wizard shows the local Ollama server URL field
- **AND** it does not require an API key
- **AND** it provides a link or route to installation and model-pull guidance

### Requirement: Local Ollama guidance must be available in app help

The app SHALL include a dedicated help topic that explains how to install Ollama, start or verify the local server, pull recommended models, and map those models to PhotoRAG capabilities.

#### Scenario: User opens local Ollama help

- **WHEN** a user opens the help topic for local Ollama
- **THEN** they see a link to the official Ollama download page
- **AND** they see the default local server URL `http://localhost:11434`
- **AND** they see commands for checking the server and pulling models
- **AND** they see a table mapping PhotoRAG capabilities to recommended Ollama models

#### Scenario: User chooses an embedding model through Ollama

- **WHEN** a user configures the embedding capability with Ollama
- **THEN** the UI suggests Ollama embedding models such as `nomic-embed-text` and `mxbai-embed-large`
- **AND** the help topic explains that embedding models power semantic search

### Requirement: Privacy copy must distinguish local Ollama from cloud APIs

Privacy warnings and help content SHALL distinguish between cloud API providers and an Ollama server running on the user's own computer.

#### Scenario: User reviews model privacy guidance

- **WHEN** a user reads model configuration privacy guidance
- **THEN** cloud providers are described as sending data to third-party services
- **AND** local Ollama on `localhost` is described as staying on the user's computer
- **AND** non-local Ollama or custom server URLs are described according to the server the user configured
