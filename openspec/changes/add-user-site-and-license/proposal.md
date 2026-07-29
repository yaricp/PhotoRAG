# Change: Add LICENSE, honest platform-support docs, and a user-facing GitHub Pages site

## Why

The repository has no LICENSE file, blocking legal use/contribution. The README points end users at a developer-oriented `README-installer.md` with no honest signal about which platforms actually work. There is no public-facing entry point (landing page) for end users, and no way to point them at downloads without sending them into the raw repository. This is preparatory work for eventually making the repository public.

A prior, never-merged commit (`2328f2e` on the abandoned branch `worktree-feature+setupwizard-i18n-privacy`) already did solid work here: a MIT `LICENSE` with a note about the NLLB-200 translation model, a full `THIRD-PARTY-NOTICES.md` dependency audit, and an in-app setup-wizard warning about NLLB-200's CC BY-NC 4.0 (non-commercial) license. This change recovers and ships that work instead of redoing it.

## What Changes

- **Licensing**: cherry-pick the recovered commit (LICENSE, THIRD-PARTY-NOTICES.md, SetupWizard NLLB-200 warning in UI + i18n). Add a `License: MIT` line to the root README.
- **Platform support documentation** (status-only, no installer debugging in this change): an honest status matrix — macOS tested working; Windows/Linux x64 build in CI but have known post-install issues; Linux arm64 fails to build in CI (cross-compilation bug). Open a tracking GitHub issue ("Known issues: Windows/Linux installer problems", `help wanted`) that the matrix links to. Add short caveats to `README-installer.md`'s Windows/Linux sections.
- **User site**: a static one-page site under `site/` (plain HTML/CSS, no build step, system font stack) with a hero + download button (linking to `releases/latest`), a feature list, the platform matrix, and a footer linking to `README-installer.md` and the known-issues GitHub issue. No screenshots yet (placeholder comment left for a future PR — screenshots are not available in this task).
- **CI/CD**: `.github/workflows/pages.yml` deploying `site/` to GitHub Pages on push to `main` (path-filtered to `site/**`) plus manual dispatch, using the standard `configure-pages` / `upload-pages-artifact` / `deploy-pages` actions.
- **README link swap**: the root README's pointer to `README-installer.md` is replaced with a "📖 User Guide" link to the deployed site.

## Non-goals

- No debugging or fixing of the actual Windows/Linux/Linux-arm64 installer or runtime bugs — that is separate, larger, future work.
- No screenshots — a follow-up PR once assets exist.
- No Patreon/donation link — the user will provide the URL later; adding an empty placeholder is out of scope.
- **Making the repository public and enabling GitHub Pages is explicitly out of scope for this change.** GitHub Pages publishing is unavailable for private repositories on the Free plan (confirmed for this account), so the deployed site cannot go live until the repository is made public — a separate, explicit decision for the user to make.

## Impact

- Affected specs: `licensing` (new), `platform-support-docs` (new), `user-site` (new)
- Affected/added files: `LICENSE`, `THIRD-PARTY-NOTICES.md`, `frontend/src/pages/SetupWizard/{models.ts,StepModelPicker.tsx,SetupWizard.css}`, `frontend/src/i18n/locales/{en,ru,es}.json`, `README.md`, `README-installer.md`, `site/index.html`, `site/styles.css`, `site/assets/`, `.github/workflows/pages.yml`
- Verification: frontend test suite + `tsc --noEmit` after the cherry-pick; manual HTML review of the site (cannot fully verify live Pages deployment until the repo is public — documented as a follow-up task requiring explicit user approval).
