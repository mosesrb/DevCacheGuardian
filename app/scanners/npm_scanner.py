import subprocess
from pathlib import Path
import platform

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, expand_path, get_dir_size


class NpmScanner(BaseScanner):
    name = "npm / pnpm / yarn"
    ecosystem = "Node.js"
    icon = "nodejs"

    def scan(self) -> ScanResult:
        items = []
        errors = []

        # npm
        npm_path = self._get_npm_cache()
        if npm_path and Path(npm_path).exists():
            size = get_dir_size(npm_path, stop_event=self._stop)
            items.append(CacheItem(
                id="npm_cache",
                name="npm cache",
                ecosystem=self.ecosystem,
                path=npm_path,
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="npm package download cache",
                long_description=(
                    "Cached npm packages and metadata. Safe to delete — npm will re-download "
                    "packages as needed. Running 'npm cache verify' first is good practice."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="npm cache clean --force",
                icon_name="nodejs",
            ))

        # pnpm
        pnpm_path = self._get_pnpm_store()
        if pnpm_path and Path(pnpm_path).exists():
            size = get_dir_size(pnpm_path, stop_event=self._stop)
            items.append(CacheItem(
                id="pnpm_store",
                name="pnpm store",
                ecosystem=self.ecosystem,
                path=pnpm_path,
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="pnpm content-addressable package store",
                long_description=(
                    "pnpm uses a shared content-addressable store, so packages are only stored "
                    "once even across many projects. 'pnpm store prune' removes packages not "
                    "referenced by any project on your machine."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="pnpm store prune",
                icon_name="nodejs",
            ))

        # yarn
        yarn_path = self._get_yarn_cache()
        if yarn_path and Path(yarn_path).exists():
            size = get_dir_size(yarn_path, stop_event=self._stop)
            items.append(CacheItem(
                id="yarn_cache",
                name="yarn cache",
                ecosystem=self.ecosystem,
                path=yarn_path,
                size_bytes=size,
                risk_level=RiskLevel.SAFE,
                description="Yarn classic package cache",
                long_description=(
                    "Yarn stores downloaded packages locally to avoid re-downloading. "
                    "Safe to clean — packages will be re-fetched on next 'yarn install'."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="yarn cache clean",
                icon_name="nodejs",
            ))

        return self._make_result(items, errors)

    def _get_npm_cache(self) -> str:
        try:
            r = subprocess.run(["npm", "config", "get", "cache"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                path = r.stdout.strip()
                if path and path != "undefined":
                    return path
        except Exception:
            pass
        system = platform.system()
        home = Path.home()
        if system == "Windows":
            return expand_path("%APPDATA%/npm-cache")
        elif system == "Darwin":
            return str(home / "Library/Caches/npm")
        return str(home / ".npm")

    def _get_pnpm_store(self) -> str:
        try:
            r = subprocess.run(["pnpm", "store", "path"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        home = Path.home()
        system = platform.system()
        if system == "Windows":
            return expand_path("%LOCALAPPDATA%/pnpm/store")
        elif system == "Darwin":
            return str(home / "Library/pnpm/store")
        return str(home / ".local/share/pnpm/store")

    def _get_yarn_cache(self) -> str:
        try:
            r = subprocess.run(["yarn", "cache", "dir"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        home = Path.home()
        system = platform.system()
        if system == "Windows":
            return expand_path("%LOCALAPPDATA%/Yarn/Cache")
        elif system == "Darwin":
            return str(home / "Library/Caches/yarn")
        return str(home / ".cache/yarn")
