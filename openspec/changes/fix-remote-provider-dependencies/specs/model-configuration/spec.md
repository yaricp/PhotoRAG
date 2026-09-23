# model-configuration Specification Delta

## ADDED Requirements

### Requirement: Packaged remote providers must have installed runtime support

Every remote provider exposed by the desktop UI SHALL have the Python packages and backend construction path required to run in the packaged first-run backend venv.

#### Scenario: User selects a listed cloud provider

- **WHEN** a packaged app user opens the Models page or Setup Wizard
- **AND** a provider is listed for a model capability
- **THEN** the packaged backend requirements include the provider package needed for that selection
- **AND** backend code can construct the model client for that provider without an import error caused by a missing optional package

#### Scenario: Provider is not packaged

- **WHEN** a provider package or backend implementation is not included in the packaged app
- **THEN** the provider is not offered as a selectable option for the affected model capability
- **AND** model suggestions for that provider are not shown

### Requirement: Provider support matrix must be testable

The repository SHALL contain an explicit provider support matrix that tests can compare against frontend provider options, backend provider code, and packaged Python requirements.

#### Scenario: Frontend and backend provider lists drift

- **WHEN** a developer adds, removes, or renames a provider in the Models page or Setup Wizard
- **THEN** automated tests fail unless the provider support matrix and backend/package dependency support are updated consistently

#### Scenario: Production requirements drift from development dependencies

- **WHEN** a provider package is present in `backend/pyproject.toml` but absent from `backend/requirements.txt`
- **AND** that provider is listed as packaged-supported
- **THEN** automated tests fail with a message identifying the missing production requirement
