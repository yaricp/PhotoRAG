# Change: Expand user site with download/getting-started guidance and i18n; surface it from README

## Why

The repository is now public and the GitHub Pages user site is live, but it only carries a short "what it does" blurb and a platform matrix. It has no explicit download instructions (which file is for which platform), no onboarding guidance past "click download," and no localization — even though the desktop app itself ships in English, Russian, and Spanish. Meanwhile the root README leads with developer-oriented content; a non-technical end user landing on the repo has no obvious, low-friction pointer to the site meant for them.

## What Changes

- **README.md**: add a short, prominent block right after the title — a clear heading ("Not a developer? Start here") and a single link to the Pages site — so non-technical visitors don't need to read the rest of the (developer-focused) README to find where to go.
- **Site restructuring** (`site/index.html`): reorganize into named sections — `About` (the existing "what it does" copy, unchanged), a new `Download & Install` section, and a new `Getting Started` section — placed before the existing `Platform support` matrix, which is kept as-is.
- **Download & Install section**: a table mapping platform to the actual installer filename pattern and extension, each linking to `releases/latest`: macOS universal `.dmg`, Windows x64 `.exe`, Windows arm64 `.exe`, Linux x64 `.AppImage`; Linux arm64 listed as temporarily unavailable, linking to the tracking issue. No OS auto-detection — a plain static list for every platform.
- **Getting Started section**: first-install steps (download, open, macOS Gatekeeper note linking to `README-installer.md`), then first-launch Setup Wizard (model selection), then post-install configuration using the app's actual terminology: **Settings** (language, default folder), **Models** (which AI capabilities are active), **Folders** (add a **Watcher** for automatic ongoing ingestion, or run a one-time **Scan** on an existing folder), and where to see results (**Processing**, **Gallery**).
- **Language switcher**: a vanilla-JS, no-build-step i18n layer for the site only (separate from, and not reusing, the desktop app's i18n content, since the site's copy differs entirely). Three new JSON dictionaries (`site/i18n/en.json`, `ru.json`, `es.json`) matching the app's three supported languages; `data-i18n` attributes on every translatable text node/heading in `site/index.html`; a small `site/i18n.js` that loads the right dictionary, swaps text client-side (no page reload), and persists the chosen language in `localStorage` (default `en`); a switcher control in the page header.
- **Styling** (`site/styles.css`): styles for the header language switcher and the two new sections, consistent with the existing site's plain, dependency-free CSS.

## Non-goals

- No screenshots (still tracked as separate future work).
- No OS auto-detection for the download section — a plain list for all platforms.
- No build tooling / framework introduced — plain HTML/CSS/vanilla JS only, no change to the `pages.yml` deploy workflow (still deploys `site/` as-is).
- No changes to the desktop app itself or its own i18n content.
- No fix for the Linux arm64 build or the Windows/Linux post-install issues tracked in issue #11 — this change only documents current status.

## Impact

- Affected specs: `user-site` (modifies the existing "Static one-page user site" requirement's scope, adds new requirements for download guidance, getting-started guidance, and i18n)
- Affected/added files: `README.md`, `site/index.html`, `site/styles.css`, `site/i18n/en.json`, `site/i18n/ru.json`, `site/i18n/es.json`, `site/i18n.js`
- Verification: open `site/index.html` locally in a browser; confirm all three languages render with no missing keys, no console errors, and all links (releases/latest, README-installer.md, issue #11) resolve correctly.
