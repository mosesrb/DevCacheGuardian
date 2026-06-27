# DevCache Guardian

> A personal desktop tool for reclaiming disk space from developer tool caches — built around one principle: **explain before deleting, confirm before touching anything.**

![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6-green)
![Tests](https://img.shields.io/badge/tests-134%20passing-brightgreen)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)

---

## What it does

DevCache Guardian scans your machine for developer tool caches — pip wheels, npm packages, Docker build layers, Hugging Face models, Gradle dependencies, and more — shows you exactly what it found, how much space it's using, and lets you clean it safely.

Every action requires confirmation. Every item shows the exact cleanup command before anything runs. Configuration files and credentials found inside cache directories are automatically preserved — not deleted.

**It is not a "PC cleaner."** It will not touch your project files, virtual environments, signing keystores, or anything it isn't certain about.

---

## Quick start

### Windows (double-click)

```
launch.bat
```

Checks for Python, installs dependencies if needed, and starts the app. No terminal required.

### macOS / Linux

```bash
pip3 install -r requirements.txt
python3 main.py
```

### Requirements

- Python 3.12 or later — [python.org/downloads](https://www.python.org/downloads/)
- ~50 MB disk space for PySide6

---

## What it scans

| Ecosystem | Items found | Risk |
|-----------|-------------|------|
| **Python** | pip download cache | ✅ Safe |
| **Python** | uv package cache | ✅ Safe |
| **Node.js** | npm / pnpm / yarn caches | ✅ Safe |
| **AI / ML** | Hugging Face Hub model downloads | 🟡 Review |
| **AI / ML** | Ollama local LLM model files | 🟡 Review |
| **AI / ML** | LM Studio, ComfyUI, A1111/Forge, TGWUI, KoboldCPP | 🟡 Review |
| **AI / ML** | PyTorch Hub, Whisper, Open WebUI | 🟡 Review |
| **AI / ML** | Cursor / Claude Desktop / VS Code AI caches | ✅ Safe |
| **AI / ML** | Duplicate model files across tools | 🟡 Review |
| **Docker** | BuildKit / layer build cache | ✅ Safe |
| **Docker** | Dangling (untagged) images | ✅ Safe |
| **Docker** | Stopped / exited containers | 🟡 Review |
| **Build** | Gradle dependency cache | ✅ Safe |
| **Build** | Maven local repository | ✅ Safe |
| **Build** | Cargo registry cache (tarballs only) | ✅ Safe |
| **Build** | Go module cache + build cache | ✅ Safe |
| **Build** | NuGet packages, Flutter/Dart pub cache | ✅ Safe |
| **Build** | JetBrains IDE caches, Android Studio cache | ✅ Safe |
| **System** | OS temporary folder | 🟡 Review |
| **macOS** | Xcode DerivedData | ✅ Safe |
| **Python** | `.venv` / Poetry environments | 🔴 Danger — info only |

**Risk levels:**
- ✅ **Safe** — rebuilt automatically, no data loss
- 🟡 **Review** — re-downloadable but slow or large; extra confirmation shown
- 🔴 **Danger** — deleting breaks your projects; shown as information only, no clean button

---

## Features

### Safety — two layers of protection

**Layer 1 — Risk levels:** Every cache has a risk rating. DANGER items cannot be cleaned. REVIEW items require explicit confirmation. Every cleanup shows the exact command that will run before anything happens.

**Layer 2 — Content analysis:** Before any deletion, DevCache Guardian scans inside the cache directory for configuration files, credentials, and signing keys. If it finds any, it tells you specifically what was found (`gradle.properties`, `config.json`, `credentials.toml`, etc.) and automatically preserves those files during cleanup — even if you proceed without backing them up first.

This is the safety net for cases like deleting a Gradle cache that contained `gradle.properties` with your Android project configuration.

### Dashboard

- Health score (0-100, A-F grade) reflecting how much reclaimable cache has accumulated
- Total found, safe-to-reclaim, needs-review, and protected counts
- Cache growth alerts — see what grew since your last scan
- Storage breakdown by ecosystem
- Space trend chart (last 14 scans)
- One-click "Clean safe items" button

### Cache Explorer

- Filter by risk level, ecosystem, and text search
- Multi-select with Ctrl / Shift
- Detail panel with full description, path, and exact cleanup command
- Right-click context menu: dry run, clean, rescan, copy path, open in Explorer, protect
- Export to CSV

### Dry-run mode

Before any cleanup, run a preflight simulation. The dry-run:
- Confirms the cleanup tool is installed and in PATH
- Confirms path is accessible and writable
- Estimates exactly how many bytes would be freed
- Lists any configuration files that would be preserved
- Shows the exact command that would run

Only after reviewing the results do you decide whether to proceed.

### Cleanup flow

1. Select item(s) → click Clean
2. Confirmation dialog shows space forecast, content warnings (if any), and every command that will run
3. Optional: "Back up files first" — backs up any detected config files to `~/.devcache_guardian/backups/` before deletion
4. Optional: "Dry run first" — simulate before committing
5. Progress overlay shows item-by-item progress
6. Toast confirms bytes reclaimed
7. History updated

### Reporting

Export a full audit report in **HTML**, **Markdown**, or **PDF** — includes health score, full storage breakdown, cache growth analysis, and cleanup history.

### Scheduled policies

Assign a weekly or monthly cleanup schedule to any safe cache in Settings → Scheduled Policies. DevCache Guardian checks due policies every hour and proposes cleanup — always with confirmation, never automatic.

### System tray

The app lives in your system tray. Minimize to tray, restore by double-clicking. Quick actions (scan, clean safe caches) available from the tray menu.

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `F5` / `Ctrl+R` | Re-scan all cache locations |
| `Ctrl+D` | Dry-run all safe caches |
| `Ctrl+Shift+C` | Clean all safe caches |
| `Ctrl+E` | Export report |

---

## Safety guarantees

1. **Confirmation required** — no automated deletion; every clean requires explicit confirmation
2. **Commands over raw deletion** — uses `pip cache purge`, `npm cache clean --force`, `docker builder prune`, etc. before falling back to directory removal
3. **Content analysis** — configuration files and credentials found inside cache directories are automatically preserved, not deleted
4. **Protected locations** — home root, `.ssh`, `Documents`, `Desktop`, `Downloads`, and any path you add in Settings are never touched
5. **DANGER items** — virtual environments are shown for information only; no clean button
6. **Dry-run first** — any cleanup can be simulated before it runs
7. **Directory contents only** — when removing a directory cache, only contents are deleted; the directory itself is kept
8. **Symlink-safe** — symlink targets and traversal attacks are detected and refused
9. **All-local** — nothing is sent over the network; all data lives in `~/.devcache_guardian/`

---

## Data stored locally

```
~/.devcache_guardian/
├── guardian.db            SQLite: scan history, cleanup history, preferences, protected paths
├── backups/               Pre-deletion backups of config files (when requested)
│   └── 20260623_143211_gradle_cache/
│       ├── MANIFEST.json
│       └── gradle.properties
└── logs/
    └── guardian_YYYY-MM-DD.log    Rotating daily logs, 30-day retention
```

Nothing leaves your machine.

---

## Project layout

```
devcache_guardian/
├── main.py                         Entry point & logging setup
├── launch.bat                      Windows one-click launcher
├── requirements.txt                PySide6, loguru
├── README.md                       This file
├── docs/
│   ├── architecture_design.md      Technical specification and design decisions
│   ├── project_status.md           Feature implementation status
│   └── memories.md                 Change log and decision journal
├── tests/                          134 automated tests (pytest)
└── app/
    ├── utils.py                    Shared utilities
    ├── models/                     CacheItem, ScanResult, RiskLevel, CleanupMethod
    ├── scanners/                   One module per ecosystem + BaseScanner
    ├── cleaners/                   CleanerService (real + dry-run + content-aware)
    ├── services/                   Workers, content analyzer, backup, scoring, reports
    ├── database/                   SQLite helpers (WAL, schema versioning)
    └── ui/                         All PySide6 widgets + stylesheet
```

---

## Adding a new scanner

1. Create `app/scanners/my_scanner.py` extending `BaseScanner`
2. Set `name`, `ecosystem`, and `icon` class attributes
3. Implement `scan() -> ScanResult` — use `get_dir_size(path)` for sizing
4. Return `CacheItem` objects with correct `risk_level` and `cleanup_method`
5. Add your class to `ALL_SCANNERS` in `app/scanners/__init__.py`
6. Optionally add config file patterns to `KNOWN_CONFIG_FILES` in `app/services/content_analyzer.py`

The worker, live table updates, dashboard, history, content analysis, and rescan all pick it up automatically.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

134 tests covering safety gates, content analysis, database layer, report injection safety, and health scoring. No display required — runs headless.

---

## Troubleshooting

**App doesn't start on Windows**
Make sure Python is in your PATH. Re-run the installer and check "Add Python to PATH". Then run `launch.bat` again.

**Scan finds 0 items**
Some caches only exist if you've used the tool. For Docker, the daemon must be running. For Hugging Face / Ollama, you need to have previously downloaded a model.

**Cleanup command fails**
If the tool isn't in PATH, DevCache Guardian falls back to removing the cache directory directly. Run a dry run first to see which tools are available.

**Virtual environments show as "Danger"**
Intentional. `.venv` directories are project dependencies — deleting them breaks your projects until recreated. They're listed for awareness only.

**Docker items show 0 bytes**
Docker must be running (`docker info` should work) for the scanner to query build cache and image sizes.

**Configuration files are listed as "will be preserved"**
DevCache Guardian found config files (like `gradle.properties` or `config.json`) inside the cache directory. These will be automatically skipped during cleanup — only the actual cache artifacts are deleted. Use the "Back up files first" button if you want a copy before proceeding.

---

## Version history

See [`docs/memories.md`](docs/memories.md) for the full change log with root-cause explanations.

| Version | Highlights |
|---------|-----------|
| **v9** | Content analysis (second safety guardrail), backup system, system tray, schema versioning, WAL checkpoint on exit, 134 tests |
| v8 | Full security audit, path traversal fixes, symlink guard, DB indexes, scanner error surfacing |
| v7 | Duplicate AI model detection, scheduled policies, Markdown/PDF reports, Timeline widget |
| v6 | Parallel scanner engine, health score gauge, cache growth monitoring, AI/dev ecosystem expansion |
| v5 | Status bar, space trend chart, bulk multi-select, search highlighting, copy/open/protect |
| v4 | Safety audit: path component matching, iterative tree removal, WAL mode, ignored paths |
| v3 | Rescan single item, persistent detail panel, CSV export |
| v2 | Dry-run mode, CleanWorker (threading fix), progress overlay |
| v1 | Initial release — 7 scanners, scan/clean/history/settings |
