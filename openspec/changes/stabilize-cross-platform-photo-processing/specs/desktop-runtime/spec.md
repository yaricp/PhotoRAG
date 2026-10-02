## ADDED Requirements

### Requirement: The installed application version is visible

The desktop application SHALL display its installed version in Settings or Help using Electron's runtime application version. It SHALL NOT display the frontend development package version in place of the packaged app version.

#### Scenario: User checks the installed version

- **WHEN** a user opens Settings in a packaged desktop application
- **THEN** the page displays the version reported by Electron `app.getVersion()`

#### Scenario: Version lookup is unavailable in a browser

- **WHEN** the renderer is opened outside Electron for development or tests
- **THEN** the version label remains safe and does not cause the page to fail
