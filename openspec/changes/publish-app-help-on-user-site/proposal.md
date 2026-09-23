# Change: Publish app help on the user site

## Why

The desktop app has help for every major page, including local Ollama setup, but visitors to the GitHub Pages site cannot read it before installing PhotoRAG. Maintaining a separate handwritten website guide would let the two versions drift.

## What Changes

- Add a Documentation link to the site home page and a dedicated `docs.html` page.
- Publish all desktop help topics in English, Russian, and Spanish, in the app's topic order.
- Preserve the selected site language when moving between the home page and documentation.
- Convert links between app help topics into links between website documentation topics.
- Generate the published help data from the desktop translations and topic list, and check that the committed copy is current in CI.
- Rebuild the published help data during the GitHub Pages workflow when source help changes.

## Impact

- Affected spec: `user-site`
- Affected files: `site/`, `.github/workflows/pages.yml`, `.github/workflows/ci.yml`, `Makefile`
- The site remains static HTML/CSS/JavaScript; the Pages workflow prepares JSON data from the app help before upload.
