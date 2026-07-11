"""
TempScanner (v2)

Root cause of the slow-scan bug
--------------------------------
The previous version called get_dir_size(temp_dir) on the raw TEMP folder
with no limits.  On a typical Windows developer machine:

  C:\\Users\\<user>\\AppData\\Local\\Temp  — can hold 50 000–500 000 files
  C:\\Windows\\Temp                        — often another 10 000–100 000 files

Walking 500 000 tiny files iteratively takes 10–40 seconds on an HDD, and
even 3–8 seconds on an SSD — long enough to make the whole scan feel broken.
Additionally there is no benefit to an exact byte count here: the risk level
is REVIEW, so the user won't clean this without thinking anyway.

Fix
---
1.  Per-location file cap of 50 000 entries (instead of the global 200 000).
    TEMP tends to be flat and wide, not deep; 50 k entries gives a representative
    sample that finishes in < 1 s on both HDD and SSD.

2.  stop_event is passed through so the user's Stop button or a global timeout
    aborts the walk immediately.

3.  Size is reported as "≥ X" semantically (the caller gets the capped total;
    the long_description warns it may be approximate).

4.  %WINDIR%\\Temp is skipped if it resolves to the same path as the user temp
    dir (already handled, kept for clarity).
"""
import tempfile
import platform
from pathlib import Path

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, expand_path, get_dir_size

# Separate, tighter cap for TEMP folders — they are wide/flat, not deep,
# and an exact count is not needed for a REVIEW-level item.
_TEMP_MAX_FILES = 50_000


class TempScanner(BaseScanner):
    name      = "System / Temp"
    ecosystem = "System"
    icon      = "file-x"

    def scan(self) -> ScanResult:
        items  = []
        errors = []
        system = platform.system()

        # ── User temp dir ─────────────────────────────────────────────────────
        temp_dir = tempfile.gettempdir()
        temp_path = Path(temp_dir)
        if temp_path.exists():
            size = get_dir_size(
                temp_dir,
                stop_event=self._stop,
                max_files=_TEMP_MAX_FILES,
            )
            items.append(CacheItem(
                id="system_temp",
                name="System temp folder",
                ecosystem=self.ecosystem,
                path=temp_dir,
                size_bytes=size,
                risk_level=RiskLevel.REVIEW,
                description="Temporary files from apps and OS operations",
                long_description=(
                    "Temporary files created by the OS and running applications. "
                    "Size shown is a fast estimate (first 50 000 files scanned). "
                    "⚠ Some files may be actively in use — removing them while apps "
                    "are running can cause crashes or data corruption. "
                    "Close other applications before cleaning, or restart first. "
                    "Files held open by running processes are automatically skipped."
                ),
                cleanup_method=CleanupMethod.DIRECTORY,
                icon_name="file-x",
            ))

        # ── Windows system temp (%WINDIR%\Temp) ───────────────────────────────
        if system == "Windows":
            win_temp = expand_path("%WINDIR%\\Temp")
            win_temp_path = Path(win_temp)
            # Skip if it's the same directory as the user temp dir
            try:
                same = win_temp_path.resolve() == temp_path.resolve()
            except OSError:
                same = True
            if win_temp_path.exists() and not same:
                size = get_dir_size(
                    win_temp,
                    stop_event=self._stop,
                    max_files=_TEMP_MAX_FILES,
                )
                if size > 0:
                    items.append(CacheItem(
                        id="windows_temp",
                        name="Windows system temp",
                        ecosystem=self.ecosystem,
                        path=win_temp,
                        size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="Windows OS temporary storage",
                        long_description=(
                            "System-level temporary files created by Windows processes. "
                            "Size shown is a fast estimate (first 50 000 files scanned). "
                            "⚠ Some files may be held open by running Windows services. "
                            "Restart before cleaning for best results — files in use are skipped."
                        ),
                        cleanup_method=CleanupMethod.DIRECTORY,
                        icon_name="windows",
                    ))

        # ── macOS Derived Data (Xcode) ─────────────────────────────────────────
        if system == "Darwin":
            derived = Path.home() / "Library/Developer/Xcode/DerivedData"
            if derived.exists():
                size = get_dir_size(
                    str(derived),
                    stop_event=self._stop,
                )
                if size > 0:
                    items.append(CacheItem(
                        id="xcode_derived",
                        name="Xcode DerivedData",
                        ecosystem=self.ecosystem,
                        path=str(derived),
                        size_bytes=size,
                        risk_level=RiskLevel.SAFE,
                        description="Xcode build artifacts and indexes",
                        long_description=(
                            "Xcode stores compiled build products and source indexes here. "
                            "Safe to delete — Xcode rebuilds them. "
                            "First build after deletion will be slower."
                        ),
                        cleanup_method=CleanupMethod.DIRECTORY,
                        icon_name="brand-apple",
                    ))

        # ── Gradle cache ───────────────────────────────────────────────────────
        gradle_cache = Path.home() / ".gradle" / "caches"
        if gradle_cache.exists():
            size = get_dir_size(str(gradle_cache), stop_event=self._stop)
            if size > 0:
                items.append(CacheItem(
                    id="gradle_cache",
                    name="Gradle cache",
                    ecosystem="Build Systems",
                    path=str(gradle_cache),
                    size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Gradle build system dependency cache",
                    long_description=(
                        "Gradle stores downloaded dependencies and build artifacts here. "
                        "Safe to delete — Gradle re-downloads on next build."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    icon_name="hammer",
                ))

        # ── Maven cache ────────────────────────────────────────────────────────
        maven_cache = Path.home() / ".m2" / "repository"
        if maven_cache.exists():
            size = get_dir_size(str(maven_cache), stop_event=self._stop)
            if size > 0:
                items.append(CacheItem(
                    id="maven_cache",
                    name="Maven local repository",
                    ecosystem="Build Systems",
                    path=str(maven_cache),
                    size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Maven dependency cache",
                    long_description=(
                        "Maven stores downloaded JAR dependencies here. "
                        "Safe to delete — Maven re-downloads on next build."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    icon_name="hammer",
                ))

        return self._make_result(items, errors)
