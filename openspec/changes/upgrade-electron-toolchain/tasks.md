# Tasks: upgrade-electron-toolchain

## 1. Bump dependencies
- [x] 1.1 Bump `electron`, `electron-builder`, `electron-vite` to latest stable in `frontend/package.json`; `npm install`
- [x] 1.2 `make ci-frontend` (lint + type-check + vitest) green

## 2. Local macOS build verification (the actual bug)
- [x] 2.1 `npm run dist:mac` builds successfully with the new toolchain
- [x] 2.2 Re-run the diagnostic from the original investigation: `codesign -dv --verbose=4` + `spctl -a -vvv -t execute` on the built app's main executable — confirm it no longer reports "notarization indicates this code has been revoked"
- [x] 2.3 Manual smoke test: launch the built `.app`, complete the setup wizard, confirm the backend spawns and the app reaches a working state

## 3. Regression check
- [x] 3.1 Confirm Windows/Linux build jobs don't newly break in CI with the new toolchain: win-x64, win-arm64, linux-x64 succeed. linux-arm64 still fails (pre-existing, tracked in #11) — the failure *signature* changed (`ERR_ELECTRON_BUILDER_CANNOT_EXECUTE` → `spawn snapcraft ENOENT`) due to electron-builder 26's changed default-target fallback for architectures not covered by the repo's hardcoded `linux.target[0].arch: ["x64"]` config; root cause investigated and documented on issue #11, not fixed here (out of scope)

## 4. Final acceptance (user's bar)
- [x] 4.1 Fresh install of the rebuilt `.dmg` on this Mac (mount, drag to Applications, launch) completes with zero system warnings

## 5. Review & completion
- [x] 5.1 Code review of the diff
- [ ] 5.2 security-review before merge
- [ ] 5.3 Merge per user choice; archive change (release/publish is a separate later decision)
