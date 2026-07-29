# platform-support-docs Specification

## Purpose
TBD - created by archiving change add-user-site-and-license. Update Purpose after archive.
## Requirements
### Requirement: Honest platform support status

The project SHALL publish an accurate, current platform-support status (not aspirational) covering macOS, Windows, and Linux, distinguishing "installer builds in CI" from "installed app verified working."

#### Scenario: Visitor checks platform status before downloading

- **WHEN** a visitor views the platform-support matrix (on the user site and referenced from `README-installer.md`)
- **THEN** they see macOS marked as tested and working, Windows/Linux x64 marked as building successfully but with known post-install issues (linked to a tracking GitHub issue), and Linux arm64 marked as currently failing to build

