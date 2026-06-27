import sys
import subprocess
from pathlib import Path

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, expand_path, get_dir_size


class PipScanner(BaseScanner):
    name = "pip"
    ecosystem = "Python"
    icon = "python"

    def scan(self) -> ScanResult:
        items = []
        errors = []

        # Detect pip cache directory
        cache_path = self._get_pip_cache_dir()
        if cache_path and Path(cache_path).exists():
            size = get_dir_size(cache_path)
            items.append(CacheItem(
                id="pip_cache",
                name="pip cache",
                ecosystem=self.ecosystem,
                path=cache_path,
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="Python package download cache",
                long_description=(
                    "Stores downloaded Python package wheels and source distributions. "
                    "pip reuses these to avoid re-downloading on reinstall. "
                    "Completely safe to delete — packages will simply be re-downloaded next time."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="pip cache purge",
                icon_name="python",
            ))

        return self._make_result(items, errors)

    def _get_pip_cache_dir(self) -> str:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "cache", "dir"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        # Fallbacks by platform
        import platform
        system = platform.system()
        home = Path.home()
        if system == "Windows":
            return expand_path("%LOCALAPPDATA%/pip/cache")
        elif system == "Darwin":
            return str(home / "Library/Caches/pip")
        else:
            xdg = expand_path("$XDG_CACHE_HOME")
            if xdg and xdg != "$XDG_CACHE_HOME":
                return str(Path(xdg) / "pip")
            return str(home / ".cache/pip")
