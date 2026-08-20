# DevCache Guardian

A desktop storage manager for software developers. Reclaim gigabytes of disk space from package managers, build tools, and AI models without breaking your projects.

---

## The Problem

Developer tools cache aggressively. Over months of coding, your disk fills up with:
- Pip wheels and uv tarballs you downloaded once
- Old npm, yarn, and pnpm package archives
- Multi-gigabyte Hugging Face model weights and duplicate GGUF models
- Forgotten Docker build cache layers and dangling images
- Gradle and Maven JARs from past projects
- IDE indexes and system temp files

These caches frequently take **20 GB to 100+ GB** of SSD space. Clearing them manually is tedious, and generic "PC cleaners" often delete virtual environments, keystores, or configuration files by mistake.

---

## The Core Rule

DevCache Guardian follows one strict design principle:

> **Explain before deleting. Confirm before touching anything.**

1. **No surprise deletions**: You review every item and see the exact cleanup command before anything runs.
2. **Official commands first**: The app uses `pip cache purge`, `npm cache clean --force`, and `docker builder prune` instead of raw deletion whenever possible.
3. **Configuration file protection**: If a cache directory contains configuration files (like `gradle.properties`, `config.json`, or `.pem` keys), DevCache Guardian detects them and leaves them untouched on disk during cleanup.
4. **Development environments are protected**: Virtual environments (`.venv`, Conda, Poetry) are shown for visibility, but deletion is disabled.
5. **Completely offline**: No analytics, no telemetry, and zero network calls. Everything stays on your computer.

---

## Installation & Quick Start

### Option 1: Standalone Windows App (No Python Required)
1. Download `DevCacheGuardian-v1.0.0-windows-x64.zip` from [GitHub Releases](https://github.com/mosesrb/DevCacheGuardian/releases).
2. Extract the folder and run `DevCacheGuardian.exe`.

### Option 2: Run from Source

**Requirements:** Python 3.12 or newer.

**Windows:**
```cmd
launch.bat
```
`launch.bat` checks your Python version, installs dependencies (`PySide6`, `loguru`, `qtawesome`) on first launch, and starts the app.

**macOS / Linux:**
```bash
pip install -r requirements.txt
python main.py
```

---

## Supported Caches

| Ecosystem | Tools & Cache Locations | Safety Tier |
|---|---|---|
| **Python** | `pip` cache, `uv` cache | Safe |
| **Node.js** | `npm`, `pnpm`, `yarn` caches | Safe |
| **AI / Machine Learning** | Hugging Face Hub, Ollama, LM Studio, ComfyUI, Automatic1111/Forge, Text-Gen-WebUI, KoboldCPP, Open WebUI, PyTorch Hub, Whisper | Review |
| **AI Duplicates** | Identical model weights stored across multiple AI apps (SHA256 fingerprinting) | Review |
| **Containers** | Docker BuildKit layers, dangling images, stopped containers | Safe / Review |
| **Build Systems** | Gradle, Maven, Cargo (registry tarballs), Go modules & build cache, NuGet, Flutter/Dart, Android Studio, JetBrains IDEs | Safe |
| **System** | OS Temporary directories (`%TEMP%`, `/tmp`), macOS Xcode DerivedData | Review / Safe |
| **Environments** | Python virtualenvs (`.venv`), Poetry environments, Conda environments | Danger (Info only, no clean) |

### Safety Tiers
- **Safe**: Safe to clean. Tools re-download packages automatically as needed.
- **Review**: Re-downloadable, but files may be large (e.g. 10 GB LLMs) or actively open. Requires explicit confirmation.
- **Danger**: Removing these would break active projects (e.g. project `.venv` folders). The Clean button is disabled; items are shown for visibility and age analysis only.

---

## Key Features

- **Storage Dashboard**: Health score (0–100, Grade A–F), space breakdown by ecosystem, and 14-scan growth trends.
- **Cache Explorer**: Search by name/path, filter by ecosystem and risk level, or filter by size (`> 100 MB`, `> 1 GB`, `> 5 GB`).
- **Preflight Dry Run**: Simulate any cleanup before running it to see exact disk space reclaimed and files preserved.
- **Pre-Clean Backups**: One-click automatic backup of detected configuration files to `~/.devcache_guardian/backups/`.
- **Scheduled Policies**: Set reminders for weekly or monthly cache checkups.
- **Export Reports**: Generate full storage audit reports in **HTML**, **Markdown (GFM)**, or **PDF**.
- **System Tray**: Minimize to the system tray with quick-action scan shortcuts.
- **Live Themes**: Custom Slate & Rust theme with 5 switchable accent palettes (Rust, Verdigris, Violet, Phosphor, Amber) and bundled fonts (`IBM Plex Sans` + `JetBrains Mono`).

---

## Building from Source & Packaging

### Run Tests
The test suite runs headlessly without requiring a display:
```bash
pytest tests/ -v
```

### Build Windows Executable
To package the standalone `.exe` and distribution `.zip`:
```bash
python build_windows_dist.py
```
Output files will be generated in `dist/`:
- `dist/DevCacheGuardian.exe`
- `dist/DevCacheGuardian-v1.0.0-windows-x64.zip`

---

## Local Data Storage

All application data is stored in your user profile:
```
~/.devcache_guardian/
├── guardian.db          SQLite database (scan history, cleanup logs, preferences)
├── backups/             Timestamped copies of preserved config files
└── logs/                Rotating application logs (30-day retention)
```

---

## License

This project is licensed under the [GPLv3 License](LICENSE).
