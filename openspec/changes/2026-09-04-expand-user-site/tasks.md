# Tasks: expand-user-site

## 1. README
- [x] 1.1 Add a "Not a developer? Start here" block right after the README title, linking to `https://yaricp.github.io/PhotoRAG/`

## 2. Site i18n infrastructure
- [x] 2.1 Create `site/i18n/en.json`, `site/i18n/ru.json`, `site/i18n/es.json` with keys for every translatable string used across all site sections
- [x] 2.2 Create `site/i18n.js`: loads the dictionary for the active language, applies text to all `[data-i18n]` elements, persists/reads the choice via `localStorage`, defaults to `en`
- [x] 2.3 Add a language switcher control to the page header in `site/index.html`, wired to `site/i18n.js`

## 3. Restructure existing sections with i18n
- [x] 3.1 Rename the existing "What it does" section to "About" (same content), add `data-i18n` attributes
- [x] 3.2 Add `data-i18n` attributes to the hero, platform matrix, and footer text

## 4. Download & Install section
- [x] 4.1 Add the section to `site/index.html`: table of platform -> filename pattern/extension -> link to `releases/latest`, with Linux arm64 marked unavailable (linking to issue #11)
- [x] 4.2 Add `data-i18n` attributes for all section text; add translated strings to all three JSON dictionaries

## 5. Getting Started section
- [x] 5.1 Add the section to `site/index.html`: first install -> Setup Wizard -> Settings/Models -> Folders (Watcher vs Scan) -> Processing/Gallery, grounded in the app's actual terminology
- [x] 5.2 Add `data-i18n` attributes for all section text; add translated strings to all three JSON dictionaries

## 6. Styling
- [x] 6.1 Style the header language switcher in `site/styles.css`
- [x] 6.2 Style the Download & Install table and Getting Started steps, consistent with existing site styling

## 7. Verification
- [x] 7.1 Open `site/index.html` locally in a browser; click through all three languages, confirm no missing keys (no raw `data-i18n` keys visible as text) and no console errors
- [x] 7.2 Confirm all links (releases/latest, README-installer.md, issue #11) resolve to the correct targets in each language variant

## 8. Review & completion
- [x] 8.1 Code review of the full diff (3 findings, all fixed: unhandled fetch rejection, untranslated switcher aria-label, redundant re-fetching)
- [x] 8.2 security-review before merge (no findings)
- [ ] 8.3 Merge per user choice (PR, since `main` is now protected); archive change
