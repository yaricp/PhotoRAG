# Tasks: add-user-site-and-license

## 1. Licensing (recovered work)
- [x] 1.1 Cherry-pick commit `2328f2e` (LICENSE, THIRD-PARTY-NOTICES.md, SetupWizard NLLB-200 warning + i18n) onto this branch
- [x] 1.2 Add `License: MIT` line near the top of root README.md
- [x] 1.3 Add `license = "MIT"` to `backend/pyproject.toml`; add `"license": "MIT"` to `frontend/package.json` if missing
- [x] 1.4 Verify: frontend `vitest run` + `tsc --noEmit` green after the cherry-pick

## 2. Platform support documentation
- [x] 2.1 Open GitHub issue "Known issues: Windows/Linux installer problems" with `help wanted` label
- [x] 2.2 Write the platform status matrix content (macOS working; Windows/Linux x64 build-but-issues; Linux arm64 build failure) referencing the issue
- [x] 2.3 Add short caveats to `README-installer.md` Windows/Linux sections linking to the matrix/issue

## 3. User site
- [x] 3.1 Create `site/index.html`: hero + download button (→ `releases/latest`) + feature list + platform matrix + footer (link to README-installer.md and the known-issues issue)
- [x] 3.2 Create `site/styles.css`: responsive, system font stack, no external dependencies
- [x] 3.3 Add a favicon under `site/assets/` reused from the existing app icon
- [x] 3.4 Leave an HTML comment placeholder for a future screenshots section
- [x] 3.5 Verify: open `site/index.html` locally in a browser and confirm it renders with no console errors, links resolve to the right targets

## 4. CI/CD deploy
- [x] 4.1 Add `.github/workflows/pages.yml` (configure-pages → upload-pages-artifact → deploy-pages), triggers: push to `main` path-filtered to `site/**`, plus `workflow_dispatch`
- [x] 4.2 Validate workflow YAML (actionlint or manual review); note that `deploy-pages` cannot succeed until the repository is public and Pages is enabled (Free plan limitation) — this is a separate follow-up requiring explicit user approval, not part of this change

## 5. README updates
- [ ] 5.1 Replace the root README's `README-installer.md` link with "📖 User Guide" pointing at the site URL (`https://yaricp.github.io/PhotoRAG/`)

## 6. Review & completion
- [ ] 6.1 Code review of the full diff
- [ ] 6.2 security-review before merge
- [ ] 6.3 Merge per user choice; archive change
