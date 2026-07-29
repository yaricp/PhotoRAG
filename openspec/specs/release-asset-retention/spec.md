# release-asset-retention Specification

## Purpose
TBD - created by archiving change cleanup-old-release-assets. Update Purpose after archive.
## Requirements
### Requirement: Automatic retention of installer binaries across releases

The CI system SHALL automatically retain installer binaries for only the two most recent GitHub releases (the one currently being built and the immediately preceding one), deleting binary assets — never the release page itself — from all older releases, whenever a new release build starts.

#### Scenario: New release is published

- **WHEN** a new GitHub release is created and its build workflow runs
- **THEN** a cleanup job identifies the previous release by tag name, and deletes all binary assets from every release older than that, leaving their release pages and changelogs intact

#### Scenario: Manual rebuild does not trigger cleanup

- **WHEN** the build workflow is run manually via `workflow_dispatch` (e.g., to backfill assets for an existing release)
- **THEN** no cleanup occurs — only the automatic `release: created` trigger runs the retention job

#### Scenario: Fewer than two releases exist

- **WHEN** the repository has zero or one prior releases at the time a new release is created
- **THEN** the cleanup job takes no action

