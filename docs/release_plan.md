# Release plan notes

## PhotoRAG 0.1.5

The target version for this release is explicitly fixed at 0.1.5. This overrides Release Please's commit-derived 0.2.0 suggestion for this release cycle.

This release includes the photo-processing history and recovery work, the local Ollama model-management flow, automatic context selection, and safeguards for low-detail and blank images. Remote model providers remain available across the supported desktop platforms.

## Platform verification and support limits

- **macOS:** The user tested all currently supported model variants, including local Ollama models, and confirmed the checks passed.
- **Windows:** Remote model providers were tested. Local inference through Ollama is not validated or guaranteed for this release. The observed local Ollama failures were on an x64 Windows VM emulated by an Apple Silicon Mac, not native Windows hardware.
- **Linux:** Runtime behavior has not been tested. The release workflow builds an x86_64 AppImage. Linux ARM64 is not included in the current release build matrix.

Do not claim reliable Windows local-model support until Ollama context and timeout behavior has been calibrated on native Windows x64 hardware.

## Release gates

- Keep release notes aligned with the tested platform matrix and the actual installer targets.
- Use the release workflow to prepare version 0.1.5 from the current main branch.
- Verify the macOS universal, Windows x64, Windows ARM64, and Linux x86_64 release artifacts and their versions after the build workflow completes.
- Linux runtime verification remains deferred for 0.1.5.
- This release remains unsigned and unnotarized, as 0.1.4 was.

## Auto-updates

Do not include a full auto-update implementation in 0.1.5.

Recommended staged plan:

1. Current release: manual update through the installer.
2. Next small release: update checker that detects a new version and opens the release/download page.
3. Later: download the full installer inside the app, verify SHA256, ask for confirmation, stop backend processes, run installer, quit app.
4. Defer delta/patch updates until release hosting, signing, and installer behavior are stable.

See also: docs/auto_updates.md.
