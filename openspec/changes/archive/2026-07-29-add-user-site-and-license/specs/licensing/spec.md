# Spec delta: licensing

## ADDED Requirements

### Requirement: MIT license with third-party notices

The repository SHALL include a root `LICENSE` file under the MIT license and a `THIRD-PARTY-NOTICES.md` auditing the licenses of bundled/downloaded third-party components, including any component under a non-commercial or otherwise restrictive license.

#### Scenario: Non-commercial model disclosed

- **WHEN** a user opens the setup wizard and the local translation model (NLLB-200, licensed CC BY-NC 4.0) is visible for selection
- **THEN** the wizard displays an inline warning that this model is for non-commercial use only, and `THIRD-PARTY-NOTICES.md` documents the same restriction with a suggested remote-mode alternative
