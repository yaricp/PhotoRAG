## ADDED Requirements

### Requirement: Pipeline model warnings reflect current effective configuration

PhotoRAG SHALL evaluate its pipeline model warning from current saved model configurations and relevant availability state. It SHALL refresh the warning after model changes without requiring an application restart, distinguish unconfigured models from temporarily unavailable ones, and display all warning text in the selected interface language.

#### Scenario: User configures models after first launch

- **WHEN** a user saves working vision and translation configurations after the warning first appeared
- **THEN** the warning refreshes and no longer claims those steps are unconfigured or will be skipped

#### Scenario: Local Ollama is selected

- **WHEN** a pipeline role has a saved Ollama provider and model name without an API key
- **THEN** the warning does not classify that role as unconfigured for lack of an API key

#### Scenario: Configured model is temporarily unavailable

- **WHEN** a saved model configuration exists but the corresponding provider is currently unreachable
- **THEN** the warning explains temporary unavailability without claiming that configuration is missing

#### Scenario: Language changes

- **WHEN** the interface language is Russian, English, or Spanish
- **THEN** the warning and model-role names appear in that language
