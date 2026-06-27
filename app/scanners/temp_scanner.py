import tempfile
import platform
from pathlib import Path

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, expand_path, get_dir_size


class TempScanner(BaseScanner):
    name = "System / Temp"
    ecosystem = "System"
    icon = "file-x"

    def scan(self) -> ScanResult:
        items = []
        system = platform.system()

        # Standard temp dir — REVIEW because files may be actively in use by
        # running applications; an abrupt deletion can cause crashes or data loss.
        temp_dir = tempfile.gettempdir()
        if Path(temp_dir).exists():
            size = get_dir_size(temp_dir)
            items.append(CacheItem(
                id="system_temp",
                name="System temp folder",
                ecosystem=self.ecosystem,
                path=temp_dir,
                size_bytes=size,
                risk_level=RiskLevel.REVIEW,
                description="Temporary files from apps and OS operations",
                long_description=(
                    "Temporary files created by Windows, macOS, or Linux and running applications. "
                    "⚠ Some files may be actively in use — removing them while apps are running "
                    "can cause crashes or data corruption. Close other applications before cleaning, "
                    "or restart and clean on next boot. Files in use will be skipped automatically."
                ),
                cleanup_method=CleanupMethod.DIRECTORY,
                icon_name="file-x",
            ))

        # Windows-specific: additional temp locations
        if system == "Windows":
            win_temp = expand_path("%WINDIR%\\Temp")
            if Path(win_temp).exists() and win_temp != temp_dir:
                size = get_dir_size(win_temp)
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
                            "⚠ Some files may be held open by running Windows services. "
                            "Restart before cleaning for best results — files in use are skipped."
                        ),
                        cleanup_method=CleanupMethod.DIRECTORY,
                        icon_name="windows",
                    ))

        # macOS Derived Data (Xcode)
        if system == "Darwin":
            derived = Path.home() / "Library/Developer/Xcode/DerivedData"
            if derived.exists():
                size = get_dir_size(str(derived))
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
                            "Safe to delete — Xcode rebuilds them. First build after deletion will be slower."
                        ),
                        cleanup_method=CleanupMethod.DIRECTORY,
                        icon_name="brand-apple",
                    ))

        # Gradle cache (common on all platforms)
        gradle_cache = Path.home() / ".gradle" / "caches"
        if gradle_cache.exists():
            size = get_dir_size(str(gradle_cache))
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

        # Maven cache
        maven_cache = Path.home() / ".m2" / "repository"
        if maven_cache.exists():
            size = get_dir_size(str(maven_cache))
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

        return self._make_result(items)
