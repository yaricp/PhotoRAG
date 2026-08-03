# Spec delta: release-versioning

## ADDED Requirements

### Requirement: Package version files stay in sync with release tags

The version fields in `frontend/package.json` and `backend/pyproject.toml` SHALL match the version implied by the most recent published release tag at all times, kept in sync automatically by release-please on every release.

#### Scenario: A new release is cut

- **WHEN** release-please opens and merges a release PR for a new version
- **THEN** `frontend/package.json`, `backend/pyproject.toml`, `.release-please-manifest.json`, and `CHANGELOG.md` are all updated to the same new version in that PR

### Requirement: Published installer filenames match their release tag

Installer artifacts attached to a GitHub release SHALL have filenames whose embedded version number matches that release's tag.

#### Scenario: Visitor downloads the latest release

- **WHEN** a visitor downloads an installer from the "latest" GitHub release
- **THEN** the installer's filename version matches the release tag's version
