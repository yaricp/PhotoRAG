# Change: Upgrade Electron toolchain to fix macOS Gatekeeper "malware" block

## Why

Root cause confirmed (2026-07-29, systematic debugging with reproducible evidence): the freshly-downloaded `PhotoRAG-0.1.0-universal.dmg` (from release v0.1.2) was blocked by macOS with "Malware Blocked and Moved to Trash" on install — not the known/documented "unidentified developer" Gatekeeper dialog, a much more severe verdict.

`spctl -a -vvv` on the built app's main executable reports `"notarization indicates this code has been revoked"`. This was traced to the generic Electron launcher binary itself: the exact same check run against the **completely untouched** `node_modules/electron` binary (before any of our build steps) shows the identical "revoked" verdict. Apple has denylisted the CDHash of the stock ad-hoc-signed Electron 31.7.7 macOS launcher — almost certainly because some malware campaign shipped this exact unsigned Electron build and got caught, collaterally blocking every legitimate app sharing that binary. 31.7.7 is also the final patch of the 31.x line (current stable is 43.x), so the project has been 12 majors behind, and this class of collateral denylisting risk only grows on an EOL version.

## What Changes

- Bump `electron` 31.0.1 → latest stable 43.x, `electron-builder` 24.13.3 → latest 26.x, `electron-vite` 2.3.0 → latest 5.x (electron-vite 5's peer range `^5||^6||^7` already covers our existing `vite@5.3.1` — vite/vitest are NOT bumped as part of this change).
- No changes to `hardenedRuntime`/`gatekeeperAssess` signing config, no code-signing/notarization setup — that remains a separate, later decision.
- No native Node modules exist in the dependency tree (pure JS/React runtime; the Python backend is a spawned subprocess, not a native addon), so there is no ABI-rebuild risk from the Electron major version jump.

## Non-goals

- Does not implement real Apple Developer ID signing/notarization.
- Does not fix the separately-tracked Windows/Linux installer issues (GitHub issue #11) — the toolchain bump must not newly break Windows/Linux CI builds, but no active debugging of their existing runtime problems here. (Verified outcome: win-x64/win-arm64/linux-x64 build successfully; linux-arm64 still fails as before — a pre-existing issue whose failure signature changed with this bump, root-caused and documented on #11, not fixed here.)
- Does not change the macOS "universal" (arm64+x64 fat binary) build strategy vs. per-architecture builds — a separate, unrelated decision, not revisited here.
- Does not cut a new release (e.g., v0.1.3) — this change only merges the fix to `main`; releasing is a separate, later decision.

## Impact

- Affected specs: `desktop-runtime` (new — captures the "Electron toolchain must not trigger OS malware blocks" requirement)
- Affected files: `frontend/package.json`, `frontend/package-lock.json`
- Verification: `make ci-frontend` (lint/type-check/vitest) green; local `npm run dist:mac` build; the exact `codesign`/`spctl` diagnostic that found the bug re-run against the new build and confirmed no longer "revoked"; manual smoke test (launch built app, setup wizard, backend spawns); CI still green for Windows/Linux build jobs. Final acceptance: a real fresh install of the rebuilt `.dmg` on this Mac completes with zero system warnings — the same manual test that surfaced the original bug.
