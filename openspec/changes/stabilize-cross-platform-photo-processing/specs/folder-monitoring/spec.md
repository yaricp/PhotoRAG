## ADDED Requirements

### Requirement: Watcher status timestamps are valid and meaningful

The watcher API SHALL return a timezone-defined status-update timestamp when known. The Folders page SHALL format that value in the user's locale and SHALL display a clear unavailable state for absent or invalid legacy values. It SHALL NOT display `Invalid Date` or imply that an active watcher necessarily processed a file.

#### Scenario: Active watcher has a timestamp

- **WHEN** an active watcher is returned by the API with `updated_at`
- **THEN** the Folders page displays a valid localized status-update time
- **AND** the active badge means the watcher is registered/running, not that every incoming photo completed processing

#### Scenario: Legacy watcher has no timestamp

- **WHEN** a watcher has no valid `updated_at`
- **THEN** the Folders page shows a localized unknown or not-yet-updated label instead of `Invalid Date`

#### Scenario: Folder status differs from photo processing status

- **WHEN** a watcher remains active while one of its photo runs fails
- **THEN** the watcher may remain active and the failed photo remains visible in the Processing view
