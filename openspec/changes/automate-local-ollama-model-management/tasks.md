## 1. Ollama service integration

- [x] 1.1 Add Electron IPC for local Ollama availability, installed models, streaming pulls, cancellation and deletion.
- [x] 1.2 Resolve the model storage volume conservatively and report free disk space with unknown/estimated states.
- [x] 1.3 Verify pull progress, completion, reuse, failure and deletion with focused tests.

## 2. Model configuration

- [x] 2.1 Add a third local Ollama choice in the wizard and Models page while preserving existing stored configurations.
- [x] 2.2 Require an explicit model choice, clear stale provider credentials and keep editable suggestions.
- [x] 2.3 Download chosen Ollama models during setup and after a later configuration save, deduplicating shared selections and handling failures and cancellation.
- [x] 2.4 Update Windows notices to distinguish built-in and Ollama models.
- [x] 2.5 Align suggested embedding models with backend dimensions and retrieval prefixes.
- [x] 2.6 Show nonblocking inline Ollama pull progress on the Models page and reuse an active pull for the same model.
- [x] 2.7 Retry oversized remote CLIP candidate lists in smaller groups and propagate real failures to pipeline status.

## 3. Help and management

- [x] 3.1 Add localized Ollama help modal without sidebars, a recommendation table and optional CLI section.
- [x] 3.2 Add installed Ollama models page with user-entered downloads, sizes, storage/free-space status, low-space guidance, and single/all deletion with confirmation.
- [x] 3.3 Ensure official external links open in the system browser.
- [x] 3.4 Offer a vision-capable Ollama model under 2.5 GB first for image tasks and explain its approximate size in localized help.
- [x] 3.5 Offer the compact Ollama model as an optional chat/translation suggestion and keep an explicit but unnamed Ollama choice on Windows.

## 4. Validation

- [x] 4.1 Run OpenSpec validation, frontend type check, lint, build and targeted tests.
- [x] 4.2 Review behavior in all three locales and document the Windows/macOS/Linux runtime limits that cannot be tested locally.
- [x] 4.3 Verify the nonblocking model workflow and remote CLIP error status with focused tests and full frontend/backend checks.

## 5. Candidate installers and platform verification

- [x] 5.1 Build a separately versioned macOS universal candidate from this change and inspect its bundled code and Python runtime.
- [x] 5.2 Build separately versioned Windows x64 and ARM64 candidates and inspect their bundled code and Python runtimes.
- [x] 5.3 Build separately versioned Linux x64 and ARM64 candidates and inspect their bundled code and Python runtimes.
- [ ] 5.4 Exercise the installer and Ollama workflow on macOS and Windows: first-run language/help, model pull progress, inventory/free space, cancellation, individual/all deletion and reopening an existing configuration. Linux runtime verification is deferred from 0.1.5; its installers were inspected statically.
- [x] 5.5 Rebuild all five current test installers with the compact vision model, record artifact checksums, and verify the cached Electron archives against the official release manifest.
- [x] 5.6 Build follow-up Windows test installers with the compact OCR/chat suggestions directly below the provider choice and verify their bundled UI and runtimes.
- [x] 5.7 Build and verify updated macOS universal, Windows x64/ARM64 and Linux x64/ARM64 test installers from the same source revision.
