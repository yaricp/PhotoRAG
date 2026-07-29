# Tasks: cleanup-old-release-assets

## 1. Design verification
- [x] 1.1 Dry-run the retention algorithm against the live repo's actual `gh release list` output (no deletions) — confirm it protects exactly the 2 most recent releases by tag name and correctly identifies the rest

## 2. Implementation
- [x] 2.1 Add `cleanup-old-releases` job to `.github/workflows/build.yml` (`if: github.event_name == 'release'`, no `needs`, runs parallel to the build matrix)
- [x] 2.2 Implement retention logic: list releases, exclude current tag, protect the next-most-recent by tag name, delete assets (via `gh release delete-asset`) from every other release; log each deletion; no-op if fewer than 2 releases exist
- [x] 2.3 Validate the modified workflow with `actionlint`

## 3. Review & completion
- [x] 3.1 Code review of the diff
- [x] 3.2 security-review before merge
- [x] 3.3 Merge per user choice; archive change
