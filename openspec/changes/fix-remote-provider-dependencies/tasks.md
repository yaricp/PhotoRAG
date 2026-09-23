# Tasks: fix-remote-provider-dependencies

## 1. Specify provider support
- [x] 1.1 Add the OpenSpec delta for packaged remote provider consistency
- [x] 1.2 Define the initial provider matrix for each model type before code changes

## 2. TDD: dependency and provider matrix checks
- [x] 2.1 Add a failing backend test or script-level test that maps supported providers to required Python packages
- [x] 2.2 Add a failing frontend test that asserts unsupported providers are not shown for each model type
- [x] 2.3 Add a failing consistency test that catches a provider exposed in UI without matching packaged backend support

## 3. Implement provider consistency
- [x] 3.1 Add any missing packaged provider dependencies for providers that remain supported
- [x] 3.2 Remove or hide UI provider options that are not supported in the packaged app
- [x] 3.3 Ensure provider suggestions only appear for supported provider/model-type pairs
- [x] 3.4 Improve unsupported-provider error text where backend validation can detect a mismatch
- [x] 3.5 Update `docs/release_plan.md` with the resolved `langchain-ollama` item and the new provider-consistency status

## 4. Verify
- [x] 4.1 Run the new provider consistency tests and confirm they fail before implementation and pass after
- [x] 4.2 Run targeted frontend tests for Models page and Setup Wizard provider rendering
- [x] 4.3 Run targeted backend tests for provider construction/import paths
- [x] 4.4 Run full local CI where available
