# Tasks: fix-release-versioning

## 1. Fix release-please configuration
- [x] 1.1 `release-please-config.json`: change package key `"."` → `"frontend"`; remove `version-file`; fix `backend/pyproject.toml` extra-files entry to the real `generic` schema (drop invented `search-for`/`replace-with`)
- [x] 1.2 `backend/pyproject.toml`: add `# x-release-please-version` annotation on the `version` line
- [x] 1.3 `.release-please-manifest.json`: rename key `"."` → `"frontend"` (value stays `"0.1.2"`)
- [x] 1.4 Validate `release-please-config.json` and `.release-please-manifest.json` are well-formed JSON

## 2. One-time manual reconciliation
- [ ] 2.1 Bump `frontend/package.json` `"version"` from `0.1.0` to `0.1.2`
- [ ] 2.2 Bump `backend/pyproject.toml` `version` from `0.1.0` to `0.1.2`
- [ ] 2.3 `make ci` still green after manual version bumps (version strings aren't consumed by app logic, but confirm no test asserts on them)

## 3. Verification before touching GitHub
- [ ] 3.1 Install the `release-please` CLI locally and dry-run it against this corrected config, if a non-mutating preview mode exists — confirm it would now propose bumping both `frontend/package.json` and `backend/pyproject.toml`
- [ ] 3.2 If no safe local dry-run is possible, document why and rely on manually inspecting the bot's real PR diff before merging (task 5)

## 4. Review & merge the config fix
- [ ] 4.1 Code review of the diff
- [ ] 4.2 security-review before merge
- [ ] 4.3 Merge per user choice; archive this change

## 5. Cut the real release (after the config fix is on main)
- [ ] 5.1 Manually trigger `.github/workflows/release.yml` (workflow_dispatch)
- [ ] 5.2 Inspect the resulting release-please PR: confirm it bumps `frontend/package.json` and `backend/pyproject.toml` to `0.2.0`, updates `.release-please-manifest.json` and `CHANGELOG.md` correctly
- [ ] 5.3 Merge the release-please PR — confirm it creates GitHub release `photorag-v0.2.0`
- [ ] 5.4 Confirm `build.yml` runs on the new release and uploads correctly-named installers (e.g. `PhotoRAG-0.2.0-universal.dmg`), containing the Electron 43 fix
- [ ] 5.5 Confirm `cleanup-old-releases` fires on this real `release:created` event and cleans assets from releases older than v0.1.2
- [ ] 5.6 Final check: site's Download button now resolves to the v0.2.0 release with matching-named assets
