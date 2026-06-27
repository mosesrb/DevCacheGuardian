import subprocess
from pathlib import Path
import platform

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, expand_path, get_dir_size


class UvScanner(BaseScanner):
    name = "uv"
    ecosystem = "Python"
    icon = "python"

    def scan(self) -> ScanResult:
        items = []
        errors = []

        cache_path = self._get_uv_cache_dir()
        if cache_path and Path(cache_path).exists():
            size = get_dir_size(cache_path)
            items.append(CacheItem(
                id="uv_cache",
                name="uv cache",
                ecosystem=self.ecosystem,
                path=cache_path,
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="uv package manager cache",
                long_description=(
                    "Cache used by the uv Python package manager for ultra-fast installs. "
                    "Safe to purge at any time — uv will recreate it on the next install operation."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="uv cache clean",
                icon_name="python",
            ))

        return self._make_result(items, errors)

    def _get_uv_cache_dir(self) -> str:
        try:
            result = subprocess.run(
                ["uv", "cache", "dir"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        system = platform.system()
        home = Path.home()
        if system == "Windows":
            return expand_path("%LOCALAPPDATA%/uv/cache")
        elif system == "Darwin":
            return str(home / "Library/Caches/uv")
        else:
            return str(home / ".cache/uv")
