# PhotoRAG release notes draft

PhotoRAG now provides clearer photo-processing history and recovery, with queued and active work separated from completed attempts. Users can inspect task outcomes by phase, retry individual failed work, restart eligible unfinished work in bulk, and optionally resume interrupted tasks when the application starts.

Ollama setup now includes model discovery and management, with model-aware context handling and clearer guidance for local inference. Photo processing also has stronger safeguards for low-detail and blank images, tag confidence, and near-duplicate detection.

## Platform verification

- **macOS:** All model variants currently supported by PhotoRAG were tested, including local models through Ollama. The checks passed.
- **Windows:** Only remote model providers were tested. Local model inference is not validated or guaranteed, including through Ollama. The Ollama failure observed during this test occurred in an x64 Windows virtual machine emulated on an Apple Silicon Mac and does not establish behavior on native Windows hardware.
- **Linux:** The release build provides an x86_64 AppImage. Installation and runtime behavior have not yet been tested on Linux. A Linux ARM64 installer is not included in this release.

## Available installer targets

- macOS universal
- Windows x64
- Windows ARM64
- Linux x86_64 AppImage
