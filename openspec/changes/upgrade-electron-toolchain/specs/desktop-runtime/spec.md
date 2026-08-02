# Spec delta: desktop-runtime

## ADDED Requirements

### Requirement: Electron toolchain must not trigger OS-level malware blocks

The bundled Electron runtime SHALL be a version whose ad-hoc-signed macOS binary is not on Apple's Gatekeeper revocation list, verified at build time via the same diagnostic that discovered the original defect.

#### Scenario: Fresh install on macOS

- **WHEN** a user downloads, mounts, and installs the built `.dmg` on macOS
- **THEN** the app launches without a "malware blocked" or "notarization revoked" system dialog

#### Scenario: Build-time verification

- **WHEN** the macOS build is produced (`npm run dist:mac`)
- **THEN** `spctl -a -vvv -t execute` on the app's main executable does not report a revoked/denylisted signature
