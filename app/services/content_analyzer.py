"""
content_analyzer.py — Pre-deletion content analysis (v1)

Scans a cache directory BEFORE any deletion and flags files that look like
configuration, credentials, or other non-cache content.

Two layers:
  1. KNOWN_CONFIG_FILES — explicit registry of well-known tools
  2. _heuristic_check   — pattern matching for unknown tools

Used by CleanerService._handle_directory (both dry-run and real modes).
In real mode: flagged files are SKIPPED and listed in CleanResult.checks.
In dry-run:   flagged files are reported so the user knows what's protected.

The analyzer only uses os.stat() / os.scandir() — no file reads, no I/O
beyond directory listing. Fast enough to run synchronously before deletion.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


# ── Known configuration file registry ────────────────────────────────────────
# Maps cache_id (as defined in the scanner) to a list of
# (relative_glob_pattern, human_label, severity) tuples.
#
# severity:
#   "critical" — credentials / signing keys / project config  → shown in red
#   "warning"  — rebuild config / useful but not catastrophic  → shown in amber
#   "info"     — logs / metadata that might be useful          → shown in grey

KNOWN_CONFIG_FILES: dict[str, list[tuple[str, str, str]]] = {
    # Gradle
    "gradle_cache": [
        ("gradle.properties",           "Gradle build configuration",               "critical"),
        ("*.properties",                "Gradle properties file",                   "critical"),
        ("init.d/*.gradle",             "Gradle init script",                       "warning"),
        ("init.d/*.gradle.kts",         "Gradle init script (Kotlin)",              "warning"),
    ],
    # Maven
    "maven_cache": [
        ("settings.xml",                "Maven server credentials & mirrors",       "critical"),
        ("settings-security.xml",       "Maven encrypted master password",          "critical"),
        ("toolchains.xml",              "Maven toolchain configuration",            "warning"),
    ],
    # Cargo / Rust
    "cargo_cache": [
        ("credentials.toml",            "Cargo registry auth token",                "critical"),
        ("credentials",                 "Cargo legacy credentials file",            "critical"),
        ("config.toml",                 "Cargo configuration",                      "warning"),
        ("env",                         "Cargo environment overrides",              "warning"),
    ],
    "cargo_registry": [
        ("credentials.toml",            "Cargo registry auth token",                "critical"),
        ("config.toml",                 "Cargo configuration",                      "warning"),
    ],
    # Docker
    "docker_cache": [
        ("config.json",                 "Docker registry auth tokens",              "critical"),
        ("contexts/**",                 "Docker named contexts",                    "warning"),
        ("buildx/current",              "Docker BuildX current context",            "warning"),
    ],
    # Hugging Face
    "huggingface_cache": [
        ("token",                       "HuggingFace API token",                    "critical"),
        ("stored_tokens",               "HuggingFace stored tokens",                "critical"),
    ],
    # Android / Android Studio
    "android_cache": [
        ("debug.keystore",              "Android debug signing keystore",           "critical"),
        ("adb_usb.ini",                 "Android ADB USB device config",            "warning"),
    ],
    "android_studio_cache": [
        ("debug.keystore",              "Android debug signing keystore",           "critical"),
    ],
    # npm
    "npm_cache": [
        ("_logs/**",                    "npm install logs (useful for debugging)",   "info"),
    ],
    # uv
    "uv_cache": [
        ("uv.toml",                     "uv configuration file",                    "warning"),
    ],
    # Go
    "go_build_cache": [
        ("env",                         "Go environment configuration",             "warning"),
    ],
    # Ollama
    "ollama_cache": [
        (".ollama/id_ed25519",          "Ollama identity key",                      "critical"),
        (".ollama/id_ed25519.pub",      "Ollama public key",                        "warning"),
    ],
    # NuGet
    "nuget_cache": [
        ("NuGet.Config",                "NuGet feed configuration & credentials",   "critical"),
    ],
    # pip — pip's cache dirs are well-scoped; very unlikely to contain config
    # but ~/.pip/pip.conf or ~/.config/pip/pip.ini could appear if someone
    # sets PIPCACHEDIR to the config parent
    "pip_cache": [
        ("pip.conf",                    "pip configuration file",                   "warning"),
        ("pip.ini",                     "pip configuration file (Windows)",         "warning"),
    ],
}

# ── Heuristic patterns ────────────────────────────────────────────────────────
# Applied to ALL directories regardless of cache_id.
# Tuples: (filename_pattern, label, severity)

_HEURISTIC_NAME_EXACT: list[tuple[str, str, str]] = [
    # Credentials / tokens
    ("token",                   "API token file",                               "critical"),
    ("credentials",             "Credentials file",                             "critical"),
    ("credentials.toml",        "Credentials file (TOML)",                      "critical"),
    ("credentials.json",        "Credentials file (JSON)",                      "critical"),
    ("secret",                  "Secret file",                                  "critical"),
    ("secrets",                 "Secrets file",                                 "critical"),
    ("auth",                    "Authentication file",                          "critical"),
    ("auth.json",               "Authentication file (JSON)",                   "critical"),
    ("config.json",             "Configuration file (JSON) — may contain auth", "critical"),
    # Keys & certificates
    ("id_rsa",                  "RSA private key",                              "critical"),
    ("id_ed25519",              "Ed25519 private key",                          "critical"),
    ("id_ecdsa",                "ECDSA private key",                            "critical"),
    # Settings / config
    ("settings.xml",            "Settings file (XML)",                          "critical"),
    ("settings.json",           "Settings file (JSON)",                         "warning"),
    ("gradle.properties",       "Build configuration (Gradle)",                 "critical"),
    # Logs (info only)
    ("npm-debug.log",           "npm debug log",                                "info"),
]

_HEURISTIC_EXTENSION: list[tuple[str, str, str]] = [
    # Certificates and keys
    (".pem",        "PEM certificate/key file",         "critical"),
    (".p12",        "PKCS#12 keystore",                 "critical"),
    (".pfx",        "PFX keystore",                     "critical"),
    (".key",        "Private key file",                 "critical"),
    (".keystore",   "Java keystore",                    "critical"),
    (".jks",        "Java keystore",                    "critical"),
    # Config formats — only flag at root level (not deep inside cache)
    (".properties", "Properties configuration file",    "warning"),
    (".toml",       "TOML configuration file",          "warning"),
    (".ini",        "INI configuration file",           "warning"),
    (".cfg",        "Configuration file",               "warning"),
    # XML settings — flag at depth ≤ 1 only (settings.xml at root is critical)
    (".xml",        "XML file (may be config)",         "info"),
]

# Extensions that are definitely cache artifacts — never flag these
_SAFE_EXTENSIONS = {
    ".jar", ".class", ".pyc", ".pyo", ".whl", ".egg",
    ".tar", ".gz", ".bz2", ".xz", ".zst", ".zip",
    ".lock", ".log",  # logs at depth > 0 are fine
    ".json",          # at depth > 0; depth-0 config.json caught by exact name
    ".bin", ".so", ".dll", ".dylib", ".exe",
    ".idx", ".pack", ".rev",   # git pack files
    ".metadata", ".sha1", ".sha256", ".md5",
}


@dataclass
class ContentWarning:
    """Represents a single flagged file found inside a cache directory."""
    file_path: str          # Absolute path to the flagged file
    relative:  str          # Path relative to the cache root (for display)
    label:     str          # Human-readable description
    severity:  str          # "critical" | "warning" | "info"

    @property
    def icon(self) -> str:
        return {"critical": "🔴", "warning": "⚠", "info": "ℹ"}.get(self.severity, "ℹ")

    @property
    def severity_color(self) -> str:
        return {"critical": "#f87171", "warning": "#fbbf24", "info": "#6b7280"}.get(
            self.severity, "#6b7280"
        )


def analyze_directory(path: str, cache_id: str = "") -> list[ContentWarning]:
    """
    Scan *path* for configuration/credential files before deletion.

    Returns a list of ContentWarning objects (empty = safe to proceed).
    Never raises — any filesystem error is silently ignored.

    Performance: depth-limited to 3 levels, stat() only (no file reads).
    """
    root = Path(path)
    if not root.exists() or not root.is_dir():
        return []

    warnings: list[ContentWarning] = []
    seen: set[str] = set()

    registry = KNOWN_CONFIG_FILES.get(cache_id, [])

    def _add(fp: Path, label: str, severity: str):
        key = str(fp)
        if key not in seen:
            seen.add(key)
            warnings.append(ContentWarning(
                file_path=str(fp),
                relative=str(fp.relative_to(root)),
                label=label,
                severity=severity,
            ))

    def _check_file(fp: Path, depth: int):
        name = fp.name
        ext  = fp.suffix.lower()
        rel  = str(fp.relative_to(root))

        # 1. Registry check (cache_id specific)
        for pattern, label, severity in registry:
            if _glob_match(rel, pattern):
                _add(fp, label, severity)
                return

        # 2. Heuristic exact-name check
        for fname, label, severity in _HEURISTIC_NAME_EXACT:
            if name.lower() == fname.lower():
                _add(fp, label, severity)
                return

        # 3. Extension check (only at shallow depths to avoid false positives)
        if ext in _SAFE_EXTENSIONS:
            return
        if depth == 0:
            for fext, label, severity in _HEURISTIC_EXTENSION:
                if ext == fext:
                    _add(fp, label, severity)
                    return
        elif depth == 1 and ext in (".pem", ".p12", ".pfx", ".key", ".keystore", ".jks"):
            # Certs/keys are critical regardless of depth
            for fext, label, severity in _HEURISTIC_EXTENSION:
                if ext == fext:
                    _add(fp, label, severity)
                    return

    def _walk(directory: Path, depth: int):
        if depth > 3:
            return
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            _check_file(Path(entry.path), depth)
                        elif entry.is_dir(follow_symlinks=False):
                            _walk(Path(entry.path), depth + 1)
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

    _walk(root, 0)
    # Sort: critical first, then warning, then info
    _SORDER = {"critical": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: (_SORDER.get(w.severity, 3), w.relative))
    return warnings


def has_critical_warnings(warnings: list[ContentWarning]) -> bool:
    return any(w.severity == "critical" for w in warnings)


def warnings_by_severity(warnings: list[ContentWarning]) -> dict[str, list[ContentWarning]]:
    result: dict[str, list[ContentWarning]] = {"critical": [], "warning": [], "info": []}
    for w in warnings:
        result.setdefault(w.severity, []).append(w)
    return result


# ── Glob helper (simple — no fnmatch for speed) ───────────────────────────────

def _glob_match(rel_path: str, pattern: str) -> bool:
    """
    Minimal glob: supports * (single segment) and ** (any depth).
    rel_path uses forward slashes.
    """
    rel_path = rel_path.replace("\\", "/")
    pattern  = pattern.replace("\\", "/")

    if "**" not in pattern and "*" not in pattern:
        # Exact match or filename-only match
        return rel_path == pattern or rel_path.endswith("/" + pattern) or rel_path == pattern.lstrip("/")

    import fnmatch
    # fnmatch doesn't handle **, so expand to path-segment matching
    if "**" in pattern:
        parts_p = pattern.split("**")
        # Simple check: starts with prefix and ends with suffix
        prefix = parts_p[0].rstrip("/")
        suffix = parts_p[-1].lstrip("/")
        if prefix and not rel_path.startswith(prefix):
            return False
        if suffix and not rel_path.endswith(suffix):
            return False
        return True

    return fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
        rel_path.split("/")[-1], pattern
    )
