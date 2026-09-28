# Candidate build verification

## Cross-platform follow-up test installers: 0.1.5-pre.5

Built locally on 2026-09-28 from the same application source after replacing the blocking Ollama download dialog on the Models page with per-card progress and correcting remote CLIP failure handling. The application checks whether a chosen Ollama model is already installed, shares an active pull for that model, and leaves other model cards usable. Oversized remote CLIP candidate lists are retried in smaller groups; provider failures are reported as task failures.

| Target | Artifact in `frontend/dist-electron/ollama-candidate-pre.5/` | SHA-256 |
| --- | --- | --- |
| macOS universal | `PhotoRAG-0.1.5-pre.5-universal.dmg` | `c7e8facf032bcfaa5180fd6d987ecf12a96db6b12d83c515c2ce4e7581fd605b` |
| Windows x64 | `PhotoRAG-Setup-0.1.5-pre.5-x64.exe` | `7971c0831c412694647f9de26cacd7aa88970374e7fb466d46f2330a3a6d1740` |
| Windows ARM64 | `PhotoRAG-Setup-0.1.5-pre.5-arm64.exe` | `113d8ec6b9bfc0d1f0d0286d93c8b2c87d416c2480a6f5b0b021a3e6073a85b1` |
| Linux x64 | `PhotoRAG-0.1.5-pre.5-x86_64.AppImage` | `1643ad7866539ed7d04c07c19014a296981afba86206d815bf39d0dec38b11db` |
| Linux ARM64 | `PhotoRAG-0.1.5-pre.5-arm64.AppImage` | `0383b1f4e9f4165e95d433fb4acc8dad44b4e2760b2fe53d04467257298fa364` |

All five files passed `shasum -a 256 -c SHA256SUMS`. The DMG passed `hdiutil verify`. Unpacked applications reported version `0.1.5-pre.5` and contained matching Python runtimes: universal macOS, x64/ARM64 Windows and x64/ARM64 Linux. The Windows installers were inspected as NSIS executables and the Linux AppImages as architecture-matched ELF files. The packaged Windows x64 renderer was inspected for the new inline progress UI.

Frontend validation passed 307 tests, type checking, lint (14 existing warnings) and production build. Backend validation passed 422 tests with one skip. Strict OpenSpec validation passed. Electron Builder used cached Electron 43.2.0 archives previously checked against the official release manifest, with download-time checksum validation disabled for these local test builds. The DMG is unsigned and not notarized; signing of the other targets was not verified. None of these installers has yet been run on its target OS or published, so real installation and Ollama workflow checks remain in task 5.4.

## Windows follow-up test installers: 0.1.5-pre.4

Built locally on 2026-09-26 after adding `qwen3-vl:2b-instruct` to Ollama chat/translation suggestions, keeping the existing OCR suggestion, and moving the provider choice before the model field in the wizard and Models page. The model field also shows the first Ollama suggestion as its placeholder. These test installers are local and have not been run on Windows or published.

| Target | Artifact in `frontend/dist-electron/ollama-candidate-pre.4/` | SHA-256 |
| --- | --- | --- |
| Windows x64 | `PhotoRAG-Setup-0.1.5-pre.4-x64.exe` | `f25bc253f2fdc9f13e3f3c63ad4d32ca2934d1dc1775a9efcff49029e4c07562` |
| Windows ARM64 | `PhotoRAG-Setup-0.1.5-pre.4-arm64.exe` | `10c99263631b3f5e88c4e7d12df2bb962f0224e1613470a462aa7c42c813badb` |

Both checksums passed. The unpacked packages contained architecture-matched Python executables; `app.asar` reported `0.1.5-pre.4` and included the compact model in both OCR and chat suggestions. The builds used cached Electron 43.2.0 zip files previously checked against the official release manifest. Frontend validation passed 304 tests, type checking, lint (warnings only), production build, site-help synchronization, and strict OpenSpec validation. The macOS/Linux test installers below still contain the earlier `pre.3` UI.

## Cross-platform test installers: 0.1.5-pre.3

Built locally on 2026-09-26 from the current working tree, including the compact `qwen3-vl:2b-instruct` suggestion and synchronized Ollama help. Electron Builder used a metadata version override; `frontend/package.json` remains at `0.1.4` until the normal release process updates it. These files are local test candidates and have not been published.

| Target | Artifact in `frontend/dist-electron/ollama-candidate-pre.3/` | SHA-256 |
| --- | --- | --- |
| macOS universal | `PhotoRAG-0.1.5-pre.3-universal.dmg` | `92ed04bd636708ff8838b604b503b5b85bf57eeec04f6562ccccd0e121538596` |
| Windows x64 | `PhotoRAG-Setup-0.1.5-pre.3-x64.exe` | `cc36fe7189a6bc45c85ae541f7525922bfb79bff613f8f03fba31dc498ab4c62` |
| Windows ARM64 | `PhotoRAG-Setup-0.1.5-pre.3-arm64.exe` | `3aa48b0487d8f01692817955b063720ec943a30d78a64016b385253718232a8a` |
| Linux x64 | `PhotoRAG-0.1.5-pre.3-x86_64.AppImage` | `d8a6ddcfed3b3deeb3b86bfcb17c5f4f92b0cf0d3bef441a98ec70304123bdf5` |
| Linux ARM64 | `PhotoRAG-0.1.5-pre.3-arm64.AppImage` | `a56cb78e027eb7c8b5539ccf8dedef671d52574832e264703441563497818e4b` |

The same checksums are in `frontend/dist-electron/ollama-candidate-pre.3/SHA256SUMS`; all five files passed `shasum -a 256 -c SHA256SUMS`. Frontend tests passed 301/301, focused backend tests passed 18/18, and frontend type checking, site-help synchronization, and strict OpenSpec validation passed.

The macOS DMG passed `hdiutil verify`; its unpacked app passed all nine structural assertions, including a universal Python 3.13.13 executable. Both Windows installers were checked as NSIS executables, with architecture-specific Python 3.13.13 runtimes, backend files, and Electron `app.asar` in their corresponding unpacked packages. Both Linux AppImages were checked as x86-64 or AArch64 ELF files; their unpacked packages contained matching Python runtimes, backend files, and `app.asar`. Each packaged renderer inspected before intermediate cleanup included the compact model tag and Ollama model-management UI. The Linux ARM64 package's `app.asar` reported version `0.1.5-pre.3`.

Electron Builder used cached Electron 43.2.0 archives with download-time checksum validation disabled for these local candidate builds. After packaging, all six Electron archives used by the five targets matched the official Electron 43.2.0 `SHASUMS256.txt`. The macOS DMG is not signed or notarized; code-signing status on the other targets was not verified. Final publication should use normal CI checksum validation and the project's release signing process.

Linux ARM64 was built locally with an explicit `--linux AppImage --arm64` target. Its existing CI job remains disabled because the default target configuration has previously fallen back to missing `snapcraft` on the runner. No installer was run on its target OS during this build; the real Windows/macOS/Linux installation and Ollama workflow checks in task 5.4 remain open.

## Earlier test installers: 0.1.5-pre.2

The four previous candidates remain in `frontend/dist-electron/ollama-candidate/` for comparison. They precede the shared-help synchronization and compact vision-model suggestion. Use `0.1.5-pre.5` for new tests on all platforms.
