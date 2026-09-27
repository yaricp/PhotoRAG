# user-site Specification

## Purpose
TBD - created by archiving change add-user-site-and-license. Update Purpose after archive.
## Requirements
### Requirement: Static user site with automated Pages deployment

The repository SHALL contain a static user site under `site/` presenting the project to end users. Its home page SHALL include About, Download & Install, Getting Started, and platform support content. A separate documentation page SHALL be accessible from the home page. A GitHub Actions workflow SHALL publish the site to GitHub Pages when site files or source help content change.

#### Scenario: Visitor downloads the app from the site

- **WHEN** a visitor opens the site and follows a download link for their platform
- **THEN** they are taken to the GitHub repository's latest release page, where they can pick the asset matching the file mapping shown on the site

#### Scenario: Site updates deploy automatically

- **WHEN** a change is pushed to `main` under `site/**` or to the desktop help translations or topic list
- **THEN** the `pages.yml` workflow prepares current help data and redeploys the site without manual steps

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

### Requirement: Public documentation mirrors desktop help

The site SHALL publish all desktop help topics in the same order and with the same translated content for English, Russian, and Spanish. The published copy SHALL be derived from the desktop help source and checked for drift in CI.

#### Scenario: Visitor opens documentation from the home page

- **WHEN** a visitor follows the Documentation link on the home page
- **THEN** they can navigate every desktop help topic, including local Ollama guidance
- **AND** the article shows its introduction, body, examples, and external links when present

#### Scenario: Visitor follows an internal help link

- **WHEN** an article links to another desktop help topic
- **THEN** the public documentation opens the corresponding website topic
- **AND** the selected language remains active

#### Scenario: Visitor switches documentation language

- **WHEN** a visitor chooses English, Russian, or Spanish at the top of the documentation page
- **THEN** the topic list and article change to that language without a page reload
- **AND** the selected topic and language choice are preserved

#### Scenario: Desktop help changes

- **WHEN** a help topic is added, removed, reordered, or edited in the desktop source
- **THEN** the synchronization check identifies an outdated published copy
- **AND** the Pages workflow builds the published copy from the current desktop source

