# DevCache Guardian — Architecture & Design Specification

> **Document purpose:** Technical specification, design philosophy, system architecture, and decision rationale. Every significant design choice is explained with its root cause. Read this before modifying the codebase.

---

## 1. Core Philosophy

DevCache Guardian is built on a single governing principle:

> **Explain before deleting. Confirm before touching anything.**

This sounds simple but it has cascading implications for every design decision in the app. It means the app is explicitly *not* a "one click and it's all gone" PC cleaner. It is a developer tool for developers — people who understand what a Gradle cache is, who care about their signing keystores, and who will be very unhappy if the app silently nuked their Docker auth tokens.

Every feature is evaluated against three questions:

1. Does the user understand what this does before it happens?
2. Has the user explicitly confirmed they want it?
3. If something goes wrong, can the user recover?

If the answer to any of these is "no", the feature needs work.

### The Two Lines of Guardrails

**First line — Risk levels:**
Every `CacheItem` carries a `RiskLevel` (`SAFE`, `REVIEW`, `DANGER`). DANGER items cannot be cleaned — the Clean button is hidden entirely. REVIEW items require an extra acknowledgement in the confirm dialog. SAFE items still require confirmation.

**Second line — Content analysis:**
Even within SAFE caches, some directories contain mixed content: cache artifacts (safe to delete) alongside configuration files, credentials, and signing keys (catastrophic to delete). The `ContentAnalyzer` scans for these before any deletion, flags them in the UI, and automatically skips them during real deletion. This is the lesson from the Gradle `gradle.properties` incident — a "safe" cache that destroyed Android project configuration when cleaned.

---

## 2. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.12+ | Cross-platform, rich stdlib (sqlite3, tempfile, shutil, pathlib), good thread model, fast enough for I/O-bound work |
| **UI** | PySide6 (Qt6) | Native widgets on all platforms, proper QThread model for background work, LGPL license (no GPL contamination), mature |
| **Icons** | qtawesome 1.3+ | Bundles Font Awesome 5 Solid/Brands as Qt-ready `QIcon`s. Replaces emoji glyphs in nav, buttons, context menus, and tray menu. Pure Python, zero asset management. |
| **Fonts** | IBM Plex Sans + JetBrains Mono (bundled TTF, OFL) | Loaded at startup via `QFontDatabase.addApplicationFont` from `resources/fonts/`. IBM Plex Sans for all interface chrome; JetBrains Mono reserved for data — paths, sizes, timestamps, scores. The split signals "this is a value you can act on" vs "this is a label". |
| **Database** | SQLite (stdlib) | Zero extra dependency, WAL mode handles concurrent reader/writer (background thread writes history while main thread reads preferences), ACID compliant |
| **Logging** | loguru | One-line rotating log setup, structured output, no configuration boilerplate |
| **Testing** | pytest | Industry standard, excellent fixture model, parametrize support |

**Why not async?** Qt's event loop and Python's asyncio event loop don't compose cleanly. `QThread` with signals is the Qt-idiomatic way to keep the UI responsive during blocking I/O. Every subprocess call and every filesystem walk is in a `QThread` worker — never on the main thread.

---

## 3. Project Layout

```
devcache_guardian/
│
├── main.py                           Entry point — configures loguru before Qt imports
├── launch.bat                        Windows one-click launcher with auto-dependency install
├── requirements.txt                  PySide6, loguru, qtawesome
├── README.md                         User-facing documentation (GitHub)
│
├── docs/
│   ├── architecture_design.md        This file
│   ├── project_status.md             Feature implementation status
│   └── memories.md                   Change log and decision journal
│
├── tests/
│   ├── conftest.py                   Shared Qt/loguru stubs, sys.path setup
│   ├── test_cleaner_safety.py        CleanerService safety gate tests (44 tests)
│   ├── test_content_analyzer.py      ContentAnalyzer detection tests (43 tests)
│   ├── test_db.py                    Database layer tests (15 tests)
│   ├── test_report_generator.py      Report injection safety tests (21 tests)
│   └── test_scoring.py              Health score algorithm tests (14 tests)
│
└── app/
    ├── utils.py                      Shared utilities — single source of truth
    ├── models/
    │   ├── cache_item.py             CacheItem, RiskLevel, CleanupMethod
    │   └── scan_result.py            ScanResult (items + errors + name)
    ├── scanners/                     One class per ecosystem + BaseScanner
    ├── cleaners/                     CleanerService (real + dry-run modes)
    ├── services/                     QThread workers + pure-logic services
    ├── database/                     SQLite helpers (WAL mode)
    └── ui/                           All PySide6 widgets + stylesheet
```

---

## 4. Data Model

### CacheItem

The central data object. Immutable after creation by a scanner.

```python
@dataclass
class CacheItem:
    id:               str           # Unique, stable, snake_case e.g. "pip_cache"
    name:             str           # Display name e.g. "pip download cache"
    ecosystem:        str           # "Python", "Node.js", "Docker", "AI/ML" etc.
    path:             str           # Absolute path on disk
    size_bytes:       int
    risk_level:       RiskLevel     # SAFE | REVIEW | DANGER
    description:      str           # One-line shown in table
    long_description: str           # Full explanation shown in detail panel
    cleanup_method:   CleanupMethod # COMMAND | DIRECTORY | NONE
    cleanup_command:  Optional[str] # Shell command shown to user (first line executed)
    icon_name:        str           # Tabler icon name
    size_label:       str           # Computed: "1.2 GB"
```

**Design decisions:**
- `size_label` is pre-computed because it's rendered in a table that updates frequently.
- `cleanup_command` is shown to the user verbatim in the confirm dialog. If it's multi-line, only the first line is executed by CleanerService. Additional lines are reference information (e.g. `# Note: requires pip 23+`).
- `NONE` cleanup method means "show for information only, never clean". Used for venvs (DANGER) and duplicate model groups where the user must manually choose which copy to keep.

### RiskLevel

```python
class RiskLevel(str, Enum):
    SAFE   = "safe"    # Rebuilt automatically, no data loss
    REVIEW = "review"  # Re-downloadable but slow; confirm required
    DANGER = "danger"  # Deleting breaks projects; shown for info only
```

DANGER items: the Clean button is hidden in `DetailPanel`. `CleanerService.clean()` hard-refuses them (returns failure `CleanResult`) even if somehow called.

### CleanResult

Returned by `CleanerService.clean()` and `CleanerService._handle_directory()`.

```python
@dataclass
class CleanResult:
    success:          bool
    bytes_reclaimed:  float          # float to handle >2 GB AI model caches safely
    message:          str
    error:            Optional[str]
    dry_run:          bool
    checks:           List[str]      # Preflight lines shown in DryRunResultDialog
    content_warnings: List           # ContentWarning objects from pre-deletion analysis
    preserved_files:  List[str]      # Files skipped in real mode (config/credential files)
```

`bytes_reclaimed` is `float` not `int` — an `int32` signal would overflow on AI model caches that can exceed 17 GB. Qt's `Signal(float)` handles this correctly.

---

## 5. Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│                    UI Layer                          │
│  main_window.py — central orchestrator               │
│  dashboard, cache_table, history, settings, dialogs  │
└────────────────────┬────────────────────────────────┘
                     │ signals (thread-safe)
┌────────────────────▼────────────────────────────────┐
│                 Services Layer                       │
│  ScanWorker    — parallel scanner execution          │
│  CleanWorker   — sequential item cleanup             │
│  RescanWorker  — single-item refresh                 │
│  ContentAnalyzer — pre-deletion file analysis        │
│  BackupService — pre-deletion file backup            │
│  Scoring       — health score computation            │
│  ReportGenerator — HTML/Markdown/PDF export          │
└──────┬──────────────────────┬───────────────────────┘
       │                      │
┌──────▼──────┐    ┌──────────▼──────────────────────┐
│  Scanners   │    │         Cleaners Layer            │
│  (read-only)│    │  CleanerService (safe deletion)   │
└──────┬──────┘    └──────────┬───────────────────────┘
       │                      │
┌──────▼──────────────────────▼───────────────────────┐
│                  Database Layer                      │
│  db.py — SQLite WAL, schema versioning, migrations   │
│  policies.py — scheduled cleanup policies            │
└──────────────────────────────────────────────────────┘
```

**Rules:**
- UI never calls filesystem operations directly
- Scanners are read-only — they never modify anything
- CleanerService is the single point of deletion — all safety gates live here
- Database layer has no business logic (health score was extracted to `services/scoring.py`)
- Services layer has no Qt imports (except workers which extend QThread)

---

## 6. Threading Model

The golden rule: **the main thread never calls `subprocess.run()` or performs significant filesystem I/O.**

```
Main Thread (Qt event loop)
│
├── ScanWorker(QThread)
│     ThreadPoolExecutor runs all scanners in parallel
│     _MAX_WORKERS = 6 (avoid HDD thrashing)
│     Signals (thread-safe cross-thread):
│       .progress(name: str, current: int, total: int)
│       .item_found(CacheItem)   — debounced 120ms in CacheTableWidget
│       .finished(List[CacheItem])
│       .error(str)              — collected into _scan_errors list
│     _scan_active: bool flag prevents double-fire race condition
│
├── CleanWorker(QThread, items, dry_run)
│     Sequential: one item at a time (avoids concurrent dir deletion)
│     dry_run=True  → validate + collect check-lines, touch nothing
│     dry_run=False → content analysis → skip flagged files → delete → log DB
│     Signals:
│       .progress(name, current, total)
│       .item_done(cache_id, success, bytes: float, message)
│       .finished(total_bytes: float, failures: List[str], results: List)
│
└── RescanWorker(QThread, item)
      Matches scanners by ecosystem, returns updated item by id
      .done(Optional[CacheItem]) — None if item fully cleaned
      Rate-limited: _rescan_worker = None cleared in on_done callback
```

**Why sequential cleanup?** Concurrent deletion of different cache directories could cause filesystem pressure (especially on SSDs with limited write buffers) and makes error reporting ambiguous. The UX benefit of parallelism is minimal since cleanup is already fast.

**Why parallel scanning?** Scanner wall-clock time drops from ∑(times) to max(time). Some scanners (Docker, Ollama) make subprocess calls that take 1–3 seconds each. Running them concurrently is a significant UX improvement with no correctness risk since scanners are read-only.

---

## 7. CleanerService — Safety Gates

Every call to `CleanerService.clean()` passes through these gates in order. Any gate failure returns a `CleanResult(success=False)` immediately — no deletion occurs.

```
clean(item)
│
├── Gate 1: DANGER check
│   item.risk_level == DANGER → refuse immediately
│
├── Gate 2: _check_blocked(item.path)
│   ├── Resolve path to canonical form (prevents symlink bypass)
│   ├── Resolution failure → BLOCK (fail-safe)
│   ├── Path == home root → BLOCK
│   ├── Path is symlink itself → BLOCK (new in v9)
│   ├── Path not under home OR temp dir → BLOCK
│   ├── User-defined ignored paths (resolved, prefix match) → BLOCK
│   └── Protected components (.ssh, Documents, .git, Desktop...) → BLOCK
│
└── Gate 3: Content analysis (DIRECTORY method only)
    ├── analyze_directory(path, cache_id) → List[ContentWarning]
    ├── Dry run: warnings surfaced in CleanResult.checks
    └── Real run: flagged files SKIPPED during deletion
               → listed in CleanResult.preserved_files
```

**Critical implementation details:**

`_check_blocked` uses `Path.resolve()` before all comparisons. Without this, a relative path like `../../.ssh` or a symlink at `~/.cache/npm -> /etc/` would bypass the home-root check. Resolution failure is treated as a block, not a pass.

The hierarchy check requires paths to be under `home` OR under `tempdir` (resolved). When `home.parent == /` (root user, or Linux flat layout), the old `relative_to(home.parent)` test passed everything including `/etc/passwd`. The current implementation explicitly checks `under_home OR under_tmp` — a positive allowlist, not a negative blocklist.

---

## 8. Content Analysis System

### Two-Layer Architecture

**Layer 1 — Known configuration file registry** (`KNOWN_CONFIG_FILES` dict):
Maps `cache_id` to a list of `(glob_pattern, label, severity)` tuples. Covers 9 ecosystems explicitly: Gradle, Maven, Cargo, Docker, Hugging Face, Android, NuGet, uv, Go, Ollama, npm, pip.

```python
KNOWN_CONFIG_FILES = {
    "gradle_cache": [
        ("gradle.properties", "Gradle build configuration", "critical"),
        ("*.properties",      "Gradle properties file",    "critical"),
        ("init.d/*.gradle",   "Gradle init script",        "warning"),
    ],
    "docker_cache": [
        ("config.json",  "Docker registry auth tokens", "critical"),
        ("contexts/**",  "Docker named contexts",       "warning"),
    ],
    # ... etc
}
```

**Layer 2 — Heuristic classifier** (applied to ALL directories):
- Exact filename matches: `token`, `credentials`, `secret`, `id_rsa`, `id_ed25519`, `config.json`, `settings.xml`, etc.
- Extension matches at depth 0 only: `.pem`, `.p12`, `.pfx`, `.key`, `.keystore`, `.jks`, `.properties`, `.toml`, `.ini`, `.cfg`
- Extension matches at depth ≤ 1 for cryptographic material: `.pem`, `.p12`, `.pfx`, `.key`, `.keystore`, `.jks`

**Depth limiting:** The walker descends at most 3 levels. Extension-based heuristics only fire at depth 0 (root of cache directory) or depth 1 for certs. This prevents false positives from `.toml` files deep inside Cargo build artifacts.

**Safe extensions bypass heuristics:** `.jar`, `.class`, `.pyc`, `.whl`, `.tar`, `.gz`, `.lock`, `.bin`, `.so`, `.dll`, `.idx`, `.pack`, `.sha1`, etc. are always safe — no amount of naming convention triggers a warning.

### Severity Levels

| Level | Colour | Meaning |
|-------|--------|---------|
| `critical` | Red `#f87171` | Credentials, signing keys, project configuration — losing this causes immediate breakage |
| `warning` | Amber `#fbbf24` | Build configuration, init scripts — losing this requires manual reconfiguration |
| `info` | Grey `#6b7280` | Logs, metadata — losing this is inconvenient but not harmful |

### Integration Points

The analyzer runs in **both dry-run and real modes** before any deletion. In dry-run: warnings appear in `CleanResult.checks`. In real mode: `_remove_tree_counted_skipping()` receives the set of protected absolute paths and skips them, leaving them on disk. `os.rmdir()` (not `shutil.rmtree`) is used for directory removal so non-empty directories (containing preserved files) are silently skipped.

---

## 9. Database Schema

**File:** `~/.devcache_guardian/guardian.db`
**Journal mode:** WAL (Write-Ahead Logging)
**Pragma:** `synchronous=NORMAL`
**Schema version:** 2 (tracked in `preferences` table)

WAL mode is required because `CleanWorker` writes `cleanup_history` from a background thread while the main thread reads `preferences` or `ignored_paths`. WAL allows one concurrent writer plus unlimited readers without locking errors.

```sql
-- Core tables
scan_history        id, scanned_at, total_bytes, item_count, duration_seconds
cleanup_history     id, cleaned_at, cache_id, cache_name, bytes_reclaimed,
                    method, command, success, error_message
ignored_paths       id, path, added_at, reason
preferences         key, value                          (key-value store)
cleanup_policies    id, cache_id, cache_name, frequency, last_run, enabled

-- Growth tracking
scan_item_snapshots id, scan_id, cache_id, cache_name, ecosystem, size_bytes

-- Backup history (schema v2)
backup_history      id, backed_up_at, cache_name, cache_path,
                    backup_dir, file_count, trigger

-- Indexes (all critical query paths covered)
idx_scan_history_scanned_at           ON scan_history(scanned_at DESC)
idx_cleanup_history_cleaned_at        ON cleanup_history(cleaned_at DESC)
idx_cleanup_history_cache_id          ON cleanup_history(cache_id)
idx_scan_item_snapshots_scan_id       ON scan_item_snapshots(scan_id)
idx_scan_item_snapshots_cache_id      ON scan_item_snapshots(cache_id)
idx_backup_history_backed_up_at       ON backup_history(backed_up_at DESC)
idx_cleanup_policies_cache_id         ON cleanup_policies(cache_id)
```

### Schema Migration System

```python
_SCHEMA_VERSION = 2

def init_db():
    # ... create tables ...
    ver = _get_schema_version(conn)
    if ver < 2:
        conn.execute("CREATE TABLE IF NOT EXISTS backup_history ...")
        _set_schema_version(conn, 2)
    # Future: if ver < 3: ...
```

Gate each migration behind `if ver < N`. Migrations are additive (CREATE TABLE IF NOT EXISTS, ALTER TABLE ADD COLUMN). No destructive migrations. Version stored in `preferences` table as `schema_version`.

### Data Retention

`scan_item_snapshots` pruned to 90 days automatically after each `log_scan()` call. Without pruning, daily scanning on an AI workstation with 30+ model caches would accumulate ~33,000 rows/year and growth-delta JOINs would degrade noticeably. 90 days gives meaningful trend data while keeping the DB small.

---

## 10. Backup System

**Backup root:** `~/.devcache_guardian/backups/`

**Directory naming:** `{YYYYMMDD_HHMMSS}_{cache_slug}/`

**Contents:**
```
20260623_143211_gradle_cache/
├── MANIFEST.json              # metadata: created_at, cache_name, cache_path, file list
└── gradle.properties          # backed-up file (preserving relative path within cache)
```

**MANIFEST.json schema:**
```json
{
  "created_at": "2026-06-23T14:32:11",
  "cache_name": "Gradle cache",
  "cache_path": "/home/moses/.gradle",
  "files": [
    {
      "original": "/home/moses/.gradle/gradle.properties",
      "backup": "/home/moses/.devcache_guardian/backups/20260623_gradle_cache/gradle.properties",
      "relative": "gradle.properties",
      "label": "Gradle build configuration",
      "severity": "critical"
    }
  ]
}
```

The backup is purely additive — it never modifies or deletes anything. Recovery is manual (open folder in file manager) or via the History → Backups tab. The "Back up these files first" button in `ConfirmCleanDialog` calls `backup_service.backup_warnings()` and confirms with a green checkmark.

---

## 11. Health Score

**Module:** `app/services/scoring.py` (extracted from `db.py` — SRP)

**Formula:**
```python
safe_deduction   = min(40, safe_bytes_gb   × 4.0)   # max 40 pts
review_deduction = min(20, review_bytes_gb × 1.0)   # max 20 pts
score = max(0, 100 - safe_deduction - review_deduction)
```

**Rationale:** Safe caches penalise more heavily because they're risk-free to clean and their accumulation represents the clearest signal that cleanup is needed. Review caches penalise less because they represent a real decision (re-download time) not just laziness.

**Grade thresholds:** A≥90, B≥75, C≥60, D≥40, F<40.

**DANGER items don't affect the score** — they can't be cleaned, so penalising for them is not actionable.

---

## 12. Scanner Architecture

### BaseScanner

```python
class BaseScanner(ABC):
    name:      str    # Display name
    ecosystem: str    # Groups scanners in UI filters
    icon:      str    # Tabler icon name

    @abstractmethod
    def scan(self) -> ScanResult: ...

    def _make_result(self, items, errors=None) -> ScanResult: ...
```

`get_dir_size(path)` is a module-level function in `base_scanner.py` — iterative `os.scandir` walk (no recursion limit risk), `follow_symlinks=False` throughout.

### ALL_SCANNERS Registration

Currently a manual list in `app/scanners/__init__.py`. Every scanner class must be added here to be discovered by `ScanWorker`. The list is the single source of truth — the worker, UI filters, and rescan logic all derive from it.

**Known issue:** A scanner written but forgotten in the list silently doesn't run. Tests don't currently catch this. A future improvement would use `BaseScanner.__subclasses__()` for auto-discovery.

### Scanner Inventory

| Class | Ecosystem | Items found | Risk |
|-------|-----------|-------------|------|
| `PipScanner` | Python | pip wheel cache | SAFE |
| `UvScanner` | Python | uv cache | SAFE |
| `NpmScanner` | Node.js | npm, pnpm, yarn caches | SAFE |
| `HuggingFaceScanner` | AI/ML | HF Hub, Ollama, PyTorch Hub, Whisper | REVIEW |
| `AIExtendedScanner` | AI/ML | LM Studio, ComfyUI, A1111/Forge, TGWUI, KoboldCPP, Cursor, Claude Desktop, VS Code AI, Open WebUI, ForgeUI, SD general | REVIEW/SAFE |
| `DuplicateModelScanner` | AI/ML | Identical model files across tools | REVIEW |
| `DevEcosystemScanner` | Build/Dev | Cargo registry, Go modules, Go build, NuGet, Flutter pub, JetBrains, Android Studio, Android SDK | SAFE |
| `DockerScanner` | Docker | Build cache, dangling images, stopped containers | SAFE/REVIEW |
| `TempScanner` | System | OS temp, Gradle cache, Maven repo, Xcode DerivedData | REVIEW/SAFE |
| `VenvScanner` | Python | .venv dirs, Poetry venvs (with staleness analysis) | DANGER |

---

## 13. UI Architecture

### Signal Flow

```
ScanWorker.item_found  → CacheTableWidget.add_item()     [120ms debounce]
ScanWorker.finished    → MainWindow._on_scan_finished()
                           → log_scan(), log_scan_items()
                           → DashboardWidget.update_items()
                           → _show_scanner_error_banner() if _scan_errors
                           → wal_checkpoint() [on next scheduled prune]

CacheTableWidget.clean_requested   → MainWindow._on_clean_single()
CacheTableWidget.dry_run_requested → MainWindow._on_dry_run_single()
CacheTableWidget.rescan_requested  → MainWindow._on_rescan_single()
DetailPanel.show_error_requested   → MainWindow toast (open_in_explorer errors)
DashboardWidget.clean_safe_requested → MainWindow._clean_all_safe()

CleanWorker.item_done  → CacheTableWidget.mark_cleaned()
CleanWorker.finished   → MainWindow._on_clean_finished()
                           → DashboardWidget.update_items()
                           → HistoryWidget.refresh()
```

### Key UI Components

**`MainWindow`** — Central orchestrator. Never does business logic directly. Wires signals between workers and widgets. Owns the double-fire guard (`_scan_active`), the hourly policy timer, system tray icon, WAL checkpoint on exit, and keyboard shortcuts.

**`CacheTableWidget`** — Filterable/sortable table with a persistent `DetailPanel`. `_item_ids: Set[str]` provides O(1) deduplication on `add_item`. Search uses 150ms debounce. `DetailPanel` is created once and updated in-place (avoids Qt `deleteLater` async teardown flicker).

**`ConfirmCleanDialog`** — Runs content analysis at open time (synchronous, fast). Shows warning banner with backup button if critical files found. Separately presents the "Dry run first" option.

**`DryRunResultDialog`** — Shows `CleanResult.checks` per item. Now includes a "Protected files" section when `result.content_warnings` is non-empty.

**`Toast`** — Slide-in bottom-right notifications. Four levels: info (grey), success (green), warning (amber), error (red). Auto-dismiss after configurable duration.

**`SystemTrayIcon`** — Show / Scan now / Clean safe caches / Quit. Double-click to restore. Minimize-to-tray controlled by preference. Tray icon hidden on exit.

### Theme System (v9.1)

The UI theme is a three-layer architecture. Layout, spacing, and typography never change. Only the accent color layer is user-switchable.

**Layer 1 — Neutral tokens** (`app/ui/palettes.py :: NEUTRAL`)
Background levels, border weights, and text shades. Fixed across every palette. Never hardcoded in widget files.

**Layer 2 — Semantic tokens** (`app/ui/palettes.py :: SEMANTIC`)
Status colors — success (green), warning (amber), danger (red) — and their background/border variants. Fixed regardless of accent. Shared by risk badges, status bar, toast, and scanner alert banner.

**Layer 3 — Accent palettes** (`app/ui/palettes.py :: ACCENTS`)
The only layer the user switches. Five options: Rust (default), Verdigris, Violet, Phosphor, Amber. Each defines `accent`, `accent_hover`, `accent_pressed`, `accent_text`, and `on_accent` tokens.

**`app/ui/stylesheet.py`**
A `string.Template` function, not a static string. Called `build_stylesheet(palette: dict) -> str`. Receives the flattened token dict from `get_palette()` and substitutes all `$token` references. Applied at `QApplication` level (not `MainWindow`) so dialogs, tray menus, and all child widgets inherit it. Uses `string.Template` not `.format()` to avoid curly-brace conflicts with QSS syntax.

**`app/ui/theme.py :: ThemeManager`**
Singleton. Loads the persisted palette key from the preferences DB on startup (`ui_palette` preference). Exposes `set_palette(key)` which rebuilds and re-applies the stylesheet then emits `palette_changed(key)` signal. Widgets with QPainter-based custom drawing implement `apply_theme()` and connect to this signal.

**Live switching:** No restart required. `MainWindow._on_palette_changed()` re-applies the stylesheet, re-tints all icon buttons (qtawesome icons are re-created with the new accent color), and calls `apply_theme()` on every direct child widget.

**`app/ui/eco_colors.py`**
Categorical colors for ecosystem tags (Python, Node.js, Docker, AI/ML, Build Systems, System). These are *categorical*, not accent-dependent — they identify a category at a glance and never change between palettes, the same way a chart legend's colors don't follow a UI re-skin. Previously duplicated in three widget files with drifting values; now a single import.

**Font separation**
Two fonts, two roles, intentionally split:
- `IBM Plex Sans` — all interface chrome: labels, nav items, button text, dialog text
- `JetBrains Mono` — all data: filesystem paths, byte sizes, timestamps, health score numbers

This is not aesthetic. The monospace treatment on data values means columns align, sizes can be compared at a glance, and paths are readable without proportional spacing compressing long segments. The split is enforced in the QSS via `font-family: $font_mono` on `QLabel#metricValue`, `QLabel#cmdLabel`, and inline on size/path labels in table cells.

Both fonts are OFL-licensed, bundled in `resources/fonts/`, and loaded once at startup via `QFontDatabase.addApplicationFont`. Falls back silently to system monospace/sans if a font file is missing.

---

## 14. File Storage Layout

```
~/.devcache_guardian/
├── guardian.db              SQLite database (WAL mode)
│   ├── guardian.db-wal      WAL file (checkpointed on exit)
│   └── guardian.db-shm      WAL shared memory
├── backups/
│   └── {timestamp}_{slug}/
│       ├── MANIFEST.json
│       └── {relative_path_of_backed_up_file}
└── logs/
    └── guardian_YYYY-MM-DD.log    (30-day rotation)
```

Nothing leaves the machine. No telemetry, no analytics, no external connections.

---

## 15. Extension Points

### Adding a New Scanner

1. Create `app/scanners/my_scanner.py` extending `BaseScanner`
2. Implement `scan() -> ScanResult` returning `CacheItem` objects
3. Add to `ALL_SCANNERS` in `app/scanners/__init__.py`
4. Add `cache_id` entries to `KNOWN_CONFIG_FILES` in `content_analyzer.py` if the scanner's directory may contain config files

Nothing else changes. The worker, live table, dashboard, history, rescan, and content analysis all pick it up automatically.

### Adding a New Config File Pattern

Add entries to `KNOWN_CONFIG_FILES` in `app/services/content_analyzer.py`. The registry is the canonical source. If the pattern is generic enough (all tools use a certain filename for tokens), add to `_HEURISTIC_NAME_EXACT` instead.

### Adding a Schema Migration

1. Increment `_SCHEMA_VERSION` in `db.py`
2. Add `if ver < N:` block in `init_db()` after the defaults seeding
3. Only use `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN` — no destructive changes
4. Update this document

---

## 16. Testing Strategy

Tests are co-located in `tests/` and run headlessly — no display, no Qt widgets instantiated. All Qt and loguru dependencies are stubbed in `conftest.py`. Test modules that need specific module versions load them directly via `importlib.util.spec_from_file_location()` to avoid import chain pollution.

| File | What it tests | Approach |
|------|--------------|----------|
| `test_cleaner_safety.py` | All safety gates in `CleanerService._check_blocked` | Real `tmp_path` directories, real symlinks |
| `test_content_analyzer.py` | Registry and heuristic detection, depth limits, dedup | Real `tmp_path` directories with crafted file structures |
| `test_db.py` | Schema creation, migrations, all DB functions | In-memory SQLite via `get_connection` mock |
| `test_report_generator.py` | Markdown injection, HTML XSS escaping | Stub item objects, string assertions |
| `test_scoring.py` | Health score formula, grade thresholds | Pure arithmetic, no I/O |

**Current count:** 134 tests, all passing.

**Coverage gaps:** UI widget tests require a display (Qt renders to screen). Scanner path-detection tests require the actual tools installed. These are left for integration testing.
