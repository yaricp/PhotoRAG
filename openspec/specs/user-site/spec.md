# user-site Specification

## Purpose
TBD - created by archiving change add-user-site-and-license. Update Purpose after archive.
## Requirements
### Requirement: Static one-page user site with automated Pages deployment

The repository SHALL contain a static one-page site under `site/` (no build step) presenting the project to end users — an About section, a Download & Install section, a Getting Started section, and the platform support matrix — deployed automatically to GitHub Pages via a GitHub Actions workflow on changes to `site/`.

#### Scenario: Visitor downloads the app from the site

- **WHEN** a visitor opens the site and follows a download link for their platform
- **THEN** they are taken to the GitHub repository's latest release page, where they can pick the asset matching the file mapping shown on the site

#### Scenario: Site updates deploy automatically

- **WHEN** a change is pushed to `main` under `site/**`
- **THEN** the `pages.yml` workflow rebuilds and redeploys the site without manual steps

### Requirement: Download & Install guidance with per-platform file mapping

The site SHALL include a "Download & Install" section that maps each supported platform to its actual installer filename pattern and file extension, with each entry linking to the GitHub repository's latest release page.

#### Scenario: Visitor identifies the right file for their platform

- **WHEN** a visitor opens the Download & Install section
- **THEN** they see macOS (universal `.dmg`), Windows x64 (`.exe`), Windows arm64 (`.exe`), and Linux x64 (`.AppImage`) each named explicitly, with a link to the releases page

#### Scenario: Linux arm64 is clearly marked unavailable

- **WHEN** a visitor looks for a Linux arm64 download
- **THEN** the section marks it as temporarily unavailable and links to the tracking issue for the build failure, instead of presenting a dead or misleading download link

### Requirement: Getting Started guidance

The site SHALL include a "Getting Started" section covering first install through initial productive use, using the desktop app's actual terminology (Setup Wizard, Settings, Models, Folders, Watcher, Scan, Processing, Gallery).

#### Scenario: First-time visitor completes initial setup

- **WHEN** a visitor follows the Getting Started section after installing
- **THEN** they are guided through the first-launch Setup Wizard (model selection), then shown how to configure Settings (language, default folder) and Models (which AI capabilities are active)

#### Scenario: Visitor learns how to add photos for processing

- **WHEN** a visitor reaches the folder-configuration step of Getting Started
- **THEN** they learn the difference between adding a Watcher (ongoing automatic ingestion of new photos) and running a one-time Scan (recursive import of an existing folder), and where to check results (Processing, Gallery)

### Requirement: Multi-language site content

The site SHALL support the same three languages as the desktop app (English, Russian, Spanish) via a client-side language switcher, with no server-side rendering or build step, defaulting to English.

#### Scenario: Visitor switches the site language

- **WHEN** a visitor selects a different language from the header switcher
- **THEN** every section heading and body text on the page updates to the selected language immediately, without a page reload

#### Scenario: Language choice persists across visits

- **WHEN** a visitor selects a non-default language and returns to the site later
- **THEN** the site remembers their choice (via local browser storage) and renders in that language on load

