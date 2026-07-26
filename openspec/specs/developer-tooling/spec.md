# developer-tooling Specification

## Purpose
TBD - created by archiving change add-dev-readme-makefile. Update Purpose after archive.
## Requirements
### Requirement: Contributor onboarding via README and Makefile

The repository SHALL provide a root `README.md` addressed to developers/contributors and a root `Makefile` that wraps all routine development actions for both backend and frontend, so that a new contributor can go from clone to running tests using documented make targets only.

#### Scenario: Fresh clone to green tests

- **WHEN** a contributor clones the repository, installs the documented prerequisites (Python 3.13 + uv, Node 20), and runs `make init` followed by `make test`
- **THEN** dependencies for backend and frontend are installed into project-local environments and both test suites run and pass

#### Scenario: CI parity locally

- **WHEN** a contributor runs `make ci`
- **THEN** the same lint, format-check, type-check, and test commands as the GitHub Actions CI jobs execute locally and report the same result

