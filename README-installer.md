# PhotoDescriber2 — macOS Installation Guide

> **Platform status:** macOS is tested and working. Windows and Linux installers build successfully but have known post-install issues — see the [platform support matrix](https://yaricp.github.io/PhotoRAG/) and [tracking issue](https://github.com/yaricp/PhotoRAG/issues/11) before installing on those platforms. This guide currently only covers macOS in detail.

## System Requirements

| | Minimum |
|---|---|
| **macOS** | 13 Ventura or later |
| **Architecture** | Apple Silicon (M1/M2/M3) or Intel (universal binary) |
| **RAM** | 8 GB (16 GB recommended for local AI models) |
| **Disk space** | ~2 GB base install + up to 16 GB for optional AI models |
| **Internet** | Required during first-run setup (model downloads) |

---

## Installation

1. **Download** `PhotoDescriber2-x.x.x.dmg` from the Releases page.
2. **Open** the `.dmg` — a Finder window appears.
3. **Drag** `PhotoDescriber2.app` to the **Applications** folder shortcut.
4. **Eject** the disk image.

### If macOS Blocks the App (Gatekeeper)

Because the app is not yet notarized with an Apple Developer certificate, macOS may show:
> *"PhotoDescriber2 cannot be opened because it is from an unidentified developer."*

To open it anyway:
1. **Right-click** (or Control-click) `PhotoDescriber2.app` in Applications.
2. Select **Open** from the context menu.
3. Click **Open** in the confirmation dialog.

You only need to do this once.

---

## First Launch — Setup Wizard

On the very first launch, a 6-step setup wizard guides you through:

| Step | What happens |
|---|---|
| **1 — Welcome** | Overview of the setup process |
| **2 — Install Dependencies** | Python packages installed into an isolated virtual environment in `~/Library/Application Support/PhotoDescriber2/venv/` |
| **3 — Initialise Database** | SQLite database schema created |
| **4 — Choose AI Models** | Select which models to download (see table below) |
| **5 — Download Models** | Models downloaded with per-model progress bars; cancel anytime |
| **6 — Done** | Click **Launch** to open the main app |

### AI Models

| Model | Size | Required | Feature |
|---|---|---|---|
| CLIP ViT-B-32 | 330 MB | ✅ Yes | Photo tagging |
| nomic-embed-text-v1.5 | 280 MB | ✅ Yes | Semantic search |
| Qwen2-VL-2B | 6 GB | Optional | Local image descriptions |
| NLLB-200 Distilled | 2.5 GB | Optional | Auto-translation |
| TrOCR-small | 150 MB | Optional | Text extraction (OCR) |
| Qwen2.5-Coder-3B | 7 GB | Optional | Local AI assistant |

> **Tip:** You can skip all optional models on first run and download them later via **Settings → Models**.

Subsequent launches skip the wizard and open the main app directly.

---

## OCR — Tesseract

Local OCR (text extraction from photos) requires Tesseract to be installed on your system.
If it's missing, a banner will appear in the app with installation instructions.

Install via Homebrew:

```bash
brew install tesseract
```

Restart PhotoDescriber2 after installation for the banner to disappear.

---

## Data Location

All mutable data is stored in:

```
~/Library/Application Support/PhotoDescriber2/
├── db.sqlite3          ← photo library database
├── venv/               ← Python virtual environment
├── .hf_cache/          ← Hugging Face model cache
└── .env                ← local configuration overrides
```

---

## Uninstalling

1. Quit **PhotoDescriber2**.
2. Move `PhotoDescriber2.app` from **Applications** to the Trash.
3. Delete the data directory (optional — this removes all your library data):
   ```bash
   rm -rf ~/Library/Application\ Support/PhotoDescriber2/
   ```
4. Empty the Trash.

> **Note:** Deleting the data directory and reinstalling will trigger the setup wizard again on next launch.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| App doesn't open | Right-click → Open (see Gatekeeper section above) |
| Setup wizard loops | Delete `~/Library/Application Support/PhotoDescriber2/venv/` and relaunch |
| Backend doesn't start | Check Console.app for logs from `PhotoDescriber2` |
| OCR banner won't go away | Run `brew install tesseract`, then restart the app |
| Model download stuck | Click **Cancel**, relaunch, retry from **Settings → Models** |

---

## Building from Source

See [scripts/build-mac.sh](scripts/build-mac.sh) for the full build pipeline.

Requirements: macOS 13+, Node.js 20+, Xcode Command Line Tools.

```bash
git clone <repo-url>
cd Photo_describer2
bash scripts/build-mac.sh
# Output: frontend/dist-electron/PhotoDescriber2-*.dmg
```
