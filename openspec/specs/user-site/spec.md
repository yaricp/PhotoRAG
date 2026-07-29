# user-site Specification

## Purpose
TBD - created by archiving change add-user-site-and-license. Update Purpose after archive.
## Requirements
### Requirement: Static one-page user site with automated Pages deployment

The repository SHALL contain a static one-page site under `site/` (no build step) presenting the project to end users — features, platform support matrix, and a download entry point to the latest GitHub Release — and a GitHub Actions workflow that deploys it to GitHub Pages on changes to `site/`.

#### Scenario: Visitor downloads the app from the site

- **WHEN** a visitor opens the site and clicks the download button
- **THEN** they are taken to the GitHub repository's latest release page, where they can pick the asset for their platform

#### Scenario: Site updates deploy automatically

- **WHEN** a change is pushed to `main` under `site/**`
- **THEN** the `pages.yml` workflow rebuilds and redeploys the site without manual steps (deployment can only succeed once the repository is public, per GitHub Pages plan restrictions — tracked separately)

