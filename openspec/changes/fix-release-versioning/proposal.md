# Change: Fix release-please config so installer versions match release tags

## Why

`frontend/package.json` and `backend/pyproject.toml` are both stuck at version `0.1.0` even though the repo has published tags/releases up through `photorag-v0.1.2`. This means built installer filenames (e.g. `PhotoRAG-0.1.0-universal.dmg`) don't match their release tag or changelog, confusing anyone comparing a download to the release notes.

Root cause (confirmed against release-please's official docs, not guessed): `release-please-config.json` configures the package at path `"."` (repo root) with `release-type: "node"`, but `package.json` actually lives at `frontend/package.json` — release-please's `node` strategy looks for the manifest file at the package's own configured path, finds nothing at the repo root, and silently skips bumping it. Two more config bugs compound this: `version-file` is only honored by the `ruby`/`simple` strategies (not `node`, so it's dead config here), and the `backend/pyproject.toml` `extra-files` entry uses invented `search-for`/`replace-with` fields that aren't part of release-please's real schema — the `generic` updater actually requires an inline `# x-release-please-version` annotation comment in the target file itself, which was never added.

As a result, every past release-please run only ever bumped `.release-please-manifest.json` and `CHANGELOG.md`, never the actual version-bearing files.

## What Changes

- `release-please-config.json`: move the package key from `"."` to `"frontend"` (where `package.json` actually is); remove the non-functional `version-file` key; fix the `backend/pyproject.toml` extra-files entry to rely on an inline annotation instead of invented search/replace fields.
- `backend/pyproject.toml`: add the `# x-release-please-version` annotation comment next to its `version` line.
- `.release-please-manifest.json`: rename the package key from `"."` to `"frontend"` to match the corrected config.
- One-time manual reconciliation: bump `frontend/package.json` and `backend/pyproject.toml` version fields from `0.1.0` to `0.1.2` by hand, so they match the true current state (the manifest/tags) before the next automated bump runs — otherwise the next release-please run would compute its bump from the wrong (stale `0.1.0`) baseline.
- After merging this fix, manually trigger `.github/workflows/release.yml` to let release-please open its release PR for real, verify the PR correctly bumps both version files this time, then merge it to cut an actual new release. Per user decision, the computed bump is `0.1.2 → 0.2.0` (conventional-commit history since the last tag includes `feat:` commits, which take precedence over `fix:`) — accepted as-is, no commit-history rewriting.
- `package-name: "photorag"` and `bump-minor-pre-major: true` are kept unchanged — per release-please's docs, an explicit `package-name` controls the tag prefix independent of the package's directory path, so tags remain `photorag-vX.Y.Z`, preserving continuity with the existing `v0.1.0`/`v0.1.1`/`v0.1.2` tags.

## Non-goals

- Does not change the site's download link (`releases/latest` is already dynamic — verified no hardcoded version strings exist anywhere in `site/` or the READMEs).
- Does not rewrite git history or existing tags/releases.
- Does not fix unrelated release-process issues (e.g., the pre-existing linux-arm64 build failure, tracked separately in issue #11).

## Impact

- Affected specs: `release-versioning` (new)
- Affected files: `release-please-config.json`, `.release-please-manifest.json`, `frontend/package.json`, `backend/pyproject.toml`
- Verification: local dry-run of the corrected release-please config (via the `release-please` CLI, if it supports a non-mutating preview) before ever triggering the real GitHub workflow; after triggering, manually inspect the bot's actual PR diff to confirm both version files are bumped correctly before merging.
