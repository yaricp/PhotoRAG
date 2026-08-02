# Tasks: upgrade-electron-toolchain

## 1. Bump dependencies
- [ ] 1.1 Bump `electron`, `electron-builder`, `electron-vite` to latest stable in `frontend/package.json`; `npm install`
- [ ] 1.2 `make ci-frontend` (lint + type-check + vitest) green

## 2. Local macOS build verification (the actual bug)
- [ ] 2.1 `npm run dist:mac` builds successfully with the new toolchain
- [ ] 2.2 Re-run the diagnostic from the original investigation: `codesign -dv --verbose=4` + `spctl -a -vvv -t execute` on the built app's main executable — confirm it no longer reports "notarization indicates this code has been revoked"
- [ ] 2.3 Manual smoke test: launch the built `.app`, complete the setup wizard, confirm the backend spawns and the app reaches a working state

## 3. Regression check
- [ ] 3.1 Confirm Windows/Linux build jobs still succeed in CI with the new toolchain (not fixing their separate known issues — just confirming no new breakage)

## 4. Final acceptance (user's bar)
- [ ] 4.1 Fresh install of the rebuilt `.dmg` on this Mac (mount, drag to Applications, launch) completes with zero system warnings

## 5. Review & completion
- [ ] 5.1 Code review of the diff
- [ ] 5.2 security-review before merge
- [ ] 5.3 Merge per user choice; archive change (release/publish is a separate later decision)
