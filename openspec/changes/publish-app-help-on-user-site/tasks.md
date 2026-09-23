# Tasks: publish-app-help-on-user-site

## 1. Specify the site change
- [x] 1.1 Add the user-site OpenSpec delta for public documentation
- [x] 1.2 Define source-of-truth and publishing behavior

## 2. Build the documentation page
- [x] 2.1 Add a synchronization check that fails when the published help copy is absent or stale
- [x] 2.2 Generate all app help topics for English, Russian, and Spanish
- [x] 2.3 Add a Documentation link on the home page and a topic-based documentation page
- [x] 2.4 Preserve language choice and convert links between help topics
- [x] 2.5 Add responsive styling and a language switcher at the top of the documentation page

## 3. Publish and verify
- [x] 3.1 Run the help synchronization check in local and GitHub CI
- [x] 3.2 Regenerate help data in the Pages workflow when source help changes
- [x] 3.3 Verify the home link, three languages, topic navigation, Ollama topic, and mobile layout in a browser
- [x] 3.4 Validate OpenSpec and final changed-file checks
