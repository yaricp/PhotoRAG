# Spec delta: persistence

## ADDED Requirements

### Requirement: SQLite-only persistence

The backend SHALL use SQLite as its only supported database backend, with the `sqlite-vec` extension providing vector search. No other database dialects, drivers, or services SHALL be declared in dependencies, configuration, or deployment files.

#### Scenario: Backend starts with SQLite

- **WHEN** the backend starts with default configuration
- **THEN** it connects to a SQLite database file under the application data directory, loads the `sqlite-vec` extension, and enables WAL mode with a 30s busy timeout

#### Scenario: No Postgres remnants

- **WHEN** the repository is inspected
- **THEN** it contains no `pgvector` dependency, no Postgres connection-string code path, and no Postgres service definition
