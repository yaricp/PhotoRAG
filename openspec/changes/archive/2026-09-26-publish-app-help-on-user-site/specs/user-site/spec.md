# user-site Specification Delta

## MODIFIED Requirements

### Requirement: Static user site with automated Pages deployment

The repository SHALL contain a static user site under `site/` presenting the project to end users. Its home page SHALL include About, Download & Install, Getting Started, and platform support content. A separate documentation page SHALL be accessible from the home page. A GitHub Actions workflow SHALL publish the site to GitHub Pages when site files or source help content change.

#### Scenario: Visitor downloads the app from the site

- **WHEN** a visitor opens the site and follows a download link for their platform
- **THEN** they are taken to the GitHub repository's latest release page, where they can pick the asset matching the file mapping shown on the site

#### Scenario: Site updates deploy automatically

- **WHEN** a change is pushed to `main` under `site/**` or to the desktop help translations or topic list
- **THEN** the `pages.yml` workflow prepares current help data and redeploys the site without manual steps

## ADDED Requirements

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
