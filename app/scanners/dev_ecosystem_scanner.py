"""
DevEcosystemScanner — covers Rust, Go, .NET, Flutter, Java/JetBrains caches.

All items are SAFE — official cleanup commands exist or directories are
purely reconstructed caches not tied to project state.
"""
import os
import platform
from pathlib import Path

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, get_dir_size, expand_path


_SYSTEM = platform.system()
_HOME   = Path.home()


class DevEcosystemScanner(BaseScanner):
    name      = "Dev Ecosystems (Rust · Go · .NET · Flutter · Java)"
    ecosystem = "Build Systems"
    icon      = "hammer"

    def scan(self) -> ScanResult:
        items = []

        # ── Rust / Cargo ──────────────────────────────────────────────────────
        # FIX: 'cargo cache --autoclean' requires the separately-installed
        # cargo-cache crate (cargo install cargo-cache) — not a standard command.
        # Better: target ~/.cargo/registry/cache specifically (downloaded tarballs)
        # and leave ~/.cargo/registry/src intact (extracted sources, needed for builds).
        cargo_registry_cache = _HOME / ".cargo" / "registry" / "cache"
        if cargo_registry_cache.exists():
            size = get_dir_size(str(cargo_registry_cache))
            items.append(CacheItem(
                id="cargo_registry_cache",
                name="Cargo registry cache",
                ecosystem=self.ecosystem,
                path=str(cargo_registry_cache),
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="Rust/Cargo downloaded crate tarballs",
                long_description=(
                    "Cargo caches downloaded crate tarballs in this directory. "
                    "The extracted sources in ~/.cargo/registry/src/ are kept separately. "
                    "Safe to delete — Cargo re-downloads tarballs on next build as needed. "
                    "Optional: 'cargo install cargo-cache && cargo cache --autoclean' for smarter cleanup."
                ),
                cleanup_method=CleanupMethod.DIRECTORY,
                # No standard cargo command exists for this; directory removal is correct
                cleanup_command=None,
                icon_name="brand-rust",
            ))

        cargo_git = _HOME / ".cargo" / "git"
        if cargo_git.exists():
            size = get_dir_size(str(cargo_git))
            if size > 0:
                items.append(CacheItem(
                    id="cargo_git",
                    name="Cargo git checkout cache",
                    ecosystem=self.ecosystem,
                    path=str(cargo_git),
                    size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Git-sourced crate checkouts for Cargo",
                    long_description=(
                        "Cargo git checkouts for crates sourced directly from Git repositories "
                        "(e.g. git = \"https://github.com/...\" in Cargo.toml). "
                        "Safe to delete — re-fetched on next build."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    cleanup_command=None,
                    icon_name="brand-rust",
                ))

        # ── Go module cache ───────────────────────────────────────────────────
        gopath = os.environ.get("GOPATH") or str(_HOME / "go")
        go_mod_cache = Path(gopath) / "pkg" / "mod" / "cache"
        if go_mod_cache.exists():
            size = get_dir_size(str(go_mod_cache))
            items.append(CacheItem(
                id="go_module_cache",
                name="Go module download cache",
                ecosystem=self.ecosystem,
                path=str(go_mod_cache),
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="Go module proxy download cache",
                long_description=(
                    "Go stores downloaded module zip files and extracted source here. "
                    "Safe to delete — modules are re-downloaded on next 'go build' or 'go mod tidy'.\n\n"
                    "⚠ Note: 'go clean -modcache' removes ALL cached modules across ALL projects. "
                    "Your first build after cleaning will re-download everything — this may take "
                    "several minutes depending on project size."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="go clean -modcache",
                icon_name="brand-golang",
            ))

        go_build_cache_path = self._go_build_cache()
        if go_build_cache_path and go_build_cache_path.exists():
            size = get_dir_size(str(go_build_cache_path))
            if size > 0:
                items.append(CacheItem(
                    id="go_build_cache",
                    name="Go build cache",
                    ecosystem=self.ecosystem,
                    path=str(go_build_cache_path),
                    size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Go compiler build artifacts cache",
                    long_description=(
                        "The Go build cache stores compiled packages to speed up incremental builds. "
                        "Safe to delete — next build will be slower but fully correct. "
                        "Run 'go clean -cache' for the official cleanup."
                    ),
                    cleanup_method=CleanupMethod.COMMAND,
                    cleanup_command="go clean -cache",
                    icon_name="brand-golang",
                ))

        # ── .NET / NuGet ──────────────────────────────────────────────────────
        nuget_path = self._nuget_cache()
        if nuget_path and nuget_path.exists():
            size = get_dir_size(str(nuget_path))
            items.append(CacheItem(
                id="nuget_cache",
                name="NuGet package cache",
                ecosystem=self.ecosystem,
                path=str(nuget_path),
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description=".NET NuGet downloaded package cache",
                long_description=(
                    "NuGet global package cache containing downloaded .NET packages. "
                    "Safe to clear — packages are re-downloaded on next restore. "
                    "Run 'dotnet nuget locals all --clear' for official cleanup."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="dotnet nuget locals all --clear",
                icon_name="brand-csharp",
            ))

        # ── Flutter / Dart pub ────────────────────────────────────────────────
        pub_cache = self._pub_cache()
        if pub_cache and pub_cache.exists():
            size = get_dir_size(str(pub_cache))
            items.append(CacheItem(
                id="flutter_pub_cache",
                name="Flutter/Dart pub cache",
                ecosystem=self.ecosystem,
                path=str(pub_cache),
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="Flutter/Dart pub.dev package download cache",
                long_description=(
                    "Dart/Flutter packages downloaded from pub.dev. "
                    "Safe to delete — packages are re-fetched on next 'flutter pub get'. "
                    "Run 'dart pub cache clean' for official cleanup."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="dart pub cache clean",
                icon_name="brand-flutter",
            ))

        # ── JetBrains (IntelliJ, PyCharm, etc.) ──────────────────────────────
        jb_cache = self._jetbrains_cache()
        if jb_cache and jb_cache.exists():
            size = get_dir_size(str(jb_cache))
            if size > 0:
                items.append(CacheItem(
                    id="jetbrains_cache",
                    name="JetBrains IDE caches",
                    ecosystem=self.ecosystem,
                    path=str(jb_cache),
                    size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="IntelliJ IDEA / PyCharm / WebStorm index & cache",
                    long_description=(
                        "JetBrains IDEs store project indexes, caches, and compiled artifacts here. "
                        "Safe to delete — IDEs rebuild indexes on next open (may take a few minutes). "
                        "You can also use 'File → Invalidate Caches / Restart' from within the IDE."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    icon_name="brand-intellij",
                ))

        # ── Android SDK / Gradle ──────────────────────────────────────────────
        android_sdk_cache = _HOME / ".android" / "cache"
        if android_sdk_cache.exists():
            size = get_dir_size(str(android_sdk_cache))
            if size > 0:
                items.append(CacheItem(
                    id="android_sdk_cache",
                    name="Android SDK cache",
                    ecosystem=self.ecosystem,
                    path=str(android_sdk_cache),
                    size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Android SDK manager download and build cache",
                    long_description=(
                        "Android SDK manager download and build cache. "
                        "Safe to delete — SDK tools re-download on next use."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    icon_name="brand-android",
                ))

        # ── Android Studio cache ───────────────────────────────────────────────
        android_studio_path = self._android_studio_cache()
        if android_studio_path and android_studio_path.exists():
            size = get_dir_size(str(android_studio_path))
            if size > 0:
                items.append(CacheItem(
                    id="android_studio_cache",
                    name="Android Studio cache",
                    ecosystem=self.ecosystem,
                    path=str(android_studio_path),
                    size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Android Studio IDE indexes and build artifacts",
                    long_description=(
                        "Android Studio stores project indexes, Gradle caches, and "
                        "build artifacts here. Safe to delete — indexes are rebuilt "
                        "on next project open (may take a few minutes). "
                        "You can also use 'File → Invalidate Caches / Restart' from within Android Studio."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    icon_name="brand-android",
                ))

        return self._make_result(items)

    # ── platform-specific path helpers ────────────────────────────────────────

    def _go_build_cache(self) -> Path:
        if _SYSTEM == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return Path(local) / "go-build" if local else None
        elif _SYSTEM == "Darwin":
            return _HOME / "Library" / "Caches" / "go-build"
        xdg = os.environ.get("XDG_CACHE_HOME", str(_HOME / ".cache"))
        return Path(xdg) / "go-build"

    def _nuget_cache(self) -> Path:
        if _SYSTEM == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return Path(local) / "NuGet" / "Cache" if local else None
        elif _SYSTEM == "Darwin":
            return _HOME / ".nuget" / "packages"
        return _HOME / ".nuget" / "packages"

    def _pub_cache(self) -> Path:
        env = os.environ.get("PUB_CACHE")
        if env:
            return Path(env)
        if _SYSTEM == "Windows":
            appdata = os.environ.get("APPDATA", "")
            return Path(appdata) / "Pub" / "Cache" if appdata else None
        return _HOME / ".pub-cache"

    def _jetbrains_cache(self) -> Path:
        if _SYSTEM == "Windows":
            appdata = os.environ.get("APPDATA", "")
            return Path(appdata) / "JetBrains" if appdata else None
        elif _SYSTEM == "Darwin":
            return _HOME / "Library" / "Caches" / "JetBrains"
        xdg = os.environ.get("XDG_CACHE_HOME", str(_HOME / ".cache"))
        return Path(xdg) / "JetBrains"

    def _android_studio_cache(self) -> Path:
        if _SYSTEM == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return Path(local) / "Google" / "AndroidStudio" if local else None
        elif _SYSTEM == "Darwin":
            return _HOME / "Library" / "Caches" / "Google" / "AndroidStudio"
        xdg = os.environ.get("XDG_CACHE_HOME", str(_HOME / ".cache"))
        return Path(xdg) / "Google" / "AndroidStudio"
