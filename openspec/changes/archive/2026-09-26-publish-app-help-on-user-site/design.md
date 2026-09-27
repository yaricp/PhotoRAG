# Design: app help on GitHub Pages

## Source of truth

`frontend/src/pages/HelpPage/topics.ts` defines topic order. The `help` object in each `frontend/src/i18n/locales/{en,ru,es}.json` file defines the titles, introductions, bodies, and examples. `site/sync-help.mjs` validates the same topic set for all three languages and writes `site/help-content/{lang}.json` without rewriting the text.

The generated files are committed so a local static server can show the site without a build. CI runs the generator in check mode; the Pages workflow regenerates data before uploading `site/`, and also runs when the source help files change.

## Navigation and language

`site/docs.html` renders a topic list and one article at a time. The fragment identifies the selected topic, for example `docs.html#local-ollama`. The site keeps its existing language switcher and local-storage key. When the shared site translations load or change, `site/i18n.js` emits a language-change event; `site/docs.js` loads the matching help JSON and rerenders the current topic.

The browser renderer creates text nodes for help content. It converts app-internal `/help/{topic}` links to `#{topic}` and leaves external HTTPS links as external links. Paragraph breaks, line breaks, and examples follow the app help renderer.

## Verification

- Check generated help files against source content in CI.
- Review the home-to-documentation link, all 20 topic links, language persistence, internal help links, Ollama content, and narrow viewport in a browser.
