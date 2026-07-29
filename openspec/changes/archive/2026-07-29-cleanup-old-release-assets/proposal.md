# Change: Auto-clean installer binaries from old releases on each new release build

## Why

GitHub release assets accumulate: every release ships 4-5 large installer binaries (100-240 MB each). Only the latest release matters to end users; older binaries (previously ~930 MB from `v0.1.0` alone) sit unused indefinitely and were only manually cleaned up once. This should happen automatically going forward so it never needs manual attention again.

## What Changes

- Add a `cleanup-old-releases` job to `.github/workflows/build.yml`, triggered only on `release: created` (never on `workflow_dispatch`, to keep manual/debug reruns safe).
- Retention rule: keep installer assets on the current release being built and the one immediately before it (2 releases total); delete assets (not the release itself) from every older release.
- Uses `gh release list` / `gh release delete-asset` (already the pattern used elsewhere in this workflow); protects the two kept releases by tag name, not list position.

## Non-goals

- Does not delete or modify release pages, changelogs, or git tags — only binary assets.
- Does not run on manual `workflow_dispatch` builds.
- Does not change the existing per-platform build/upload steps.

## Impact

- Affected specs: `release-asset-retention` (new)
- Affected files: `.github/workflows/build.yml`
- Verification: dry-run of the retention algorithm against the live repository's actual release list (no deletions) to confirm correct protected-tag selection, plus `actionlint` on the modified workflow.
