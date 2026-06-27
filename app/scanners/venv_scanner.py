"""
VenvScanner (v6) — Python virtual environment analysis.

New in v6: last-used timestamp analysis.
The scanner records the most recent mtime of files inside the venv's
site-packages directory. This is a proxy for "last time any package
was installed/modified" — a reasonable heuristic for "last used".
The timestamp is embedded in long_description and stored as extra metadata
on the CacheItem so the UI can surface "stale" environments.

IMPORTANT: risk_level remains DANGER — no auto-clean ever.
The timestamp is informational only, per the app's core philosophy.
"""
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, get_dir_size


VENV_MARKERS = ["pyvenv.cfg", "bin/activate", "Scripts/activate.bat"]
MAX_SEARCH_DEPTH = 5
COMMON_PROJECT_ROOTS = [
    "~/projects", "~/code", "~/dev", "~/workspace", "~/src",
    "~/Documents/projects", "~/Desktop/projects", "~/repos",
]

# Stale threshold in days — purely informational label, no action taken
STALE_DAYS = 90


class VenvScanner(BaseScanner):
    name      = "Python Environments"
    ecosystem = "Python"
    icon      = "python"

    def scan(self) -> ScanResult:
        items      = []
        found_paths = set()

        for root in self._get_search_roots():
            if not root.exists():
                continue
            self._find_venvs(root, found_paths, items, depth=0)

        poetry_venv_dir = self._get_poetry_venv_dir()
        if poetry_venv_dir and poetry_venv_dir.exists():
            size = get_dir_size(str(poetry_venv_dir))
            if size > 0 and str(poetry_venv_dir) not in found_paths:
                age_str = self._age_label(poetry_venv_dir)
                items.append(CacheItem(
                    id="poetry_venvs",
                    name="Poetry virtualenvs",
                    ecosystem=self.ecosystem,
                    path=str(poetry_venv_dir),
                    size_bytes=size,
                    risk_level=RiskLevel.DANGER,
                    description=f"Poetry-managed virtual environments  {age_str}",
                    long_description=(
                        "Virtual environments managed by Poetry for all your projects. "
                        "Deleting will break every Poetry project until you run 'poetry install' again. "
                        f"{age_str}  ·  Only remove if all projects are abandoned."
                    ),
                    cleanup_method=CleanupMethod.NONE,
                    icon_name="python",
                ))

        return self._make_result(items)

    def _get_search_roots(self) -> List[Path]:
        roots = []
        for p in COMMON_PROJECT_ROOTS:
            expanded = Path(p).expanduser()
            if expanded.exists() and expanded not in roots:
                roots.append(expanded)
        return roots

    def _find_venvs(self, path: Path, found: set, items: list, depth: int):
        if depth > MAX_SEARCH_DEPTH or str(path) in found:
            return
        try:
            if self._is_venv(path):
                found.add(str(path))
                size         = get_dir_size(str(path))
                project_name = path.parent.name
                last_used    = self._last_used(path)
                age_str      = self._age_label_from_dt(last_used) if last_used else ""
                stale        = self._is_stale(last_used)

                staleness = ""
                if stale and last_used:
                    days = (datetime.now() - last_used).days
                    staleness = f"  ⚠ Possibly stale — last activity {days} days ago"

                items.append(CacheItem(
                    id=f"venv_{hash(str(path)) & 0xFFFFFF}",
                    name=f".venv ({project_name}){' ⚠' if stale else ''}",
                    ecosystem=self.ecosystem,
                    path=str(path),
                    size_bytes=size,
                    risk_level=RiskLevel.DANGER,
                    description=f"Virtual env for '{project_name}'{staleness}",
                    long_description=(
                        f"Python virtual environment at '{path}'.\n"
                        f"Project: {project_name}\n"
                        f"Last activity: {age_str or 'unknown'}\n\n"
                        "Deleting will break this project until you recreate it "
                        f"with 'python -m venv .venv && pip install -r requirements.txt'. "
                        "Only remove if you no longer need this project."
                    ),
                    cleanup_method=CleanupMethod.NONE,
                    icon_name="python",
                ))
                return

            for child in path.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    if child.name in {"node_modules", "__pycache__", ".git",
                                      "dist", "build", ".idea", ".vscode"}:
                        continue
                    self._find_venvs(child, found, items, depth + 1)
        except (PermissionError, OSError):
            pass

    def _is_venv(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        return any((path / m).exists() for m in VENV_MARKERS)

    def _last_used(self, venv_path: Path) -> Optional[datetime]:
        """Return the most recent mtime of any file in site-packages."""
        latest = None
        # Check lib/pythonX.Y/site-packages (Linux/macOS)
        for sp in venv_path.glob("lib/python*/site-packages"):
            try:
                for entry in sp.iterdir():
                    try:
                        mt = entry.stat().st_mtime
                        dt = datetime.fromtimestamp(mt)
                        if latest is None or dt > latest:
                            latest = dt
                    except OSError:
                        pass
                break  # first python version found is enough
            except OSError:
                pass
        # Windows: Lib/site-packages
        win_sp = venv_path / "Lib" / "site-packages"
        if win_sp.exists():
            try:
                for entry in win_sp.iterdir():
                    try:
                        mt = entry.stat().st_mtime
                        dt = datetime.fromtimestamp(mt)
                        if latest is None or dt > latest:
                            latest = dt
                    except OSError:
                        pass
            except OSError:
                pass
        return latest

    def _is_stale(self, last_used: Optional[datetime]) -> bool:
        if last_used is None:
            return False
        return (datetime.now() - last_used).days > STALE_DAYS

    def _age_label(self, path: Path) -> str:
        last = self._last_used(path)
        return self._age_label_from_dt(last)

    def _age_label_from_dt(self, dt: Optional[datetime]) -> str:
        if dt is None:
            return ""
        days = (datetime.now() - dt).days
        if days == 0: return "Last used: today"
        if days == 1: return "Last used: yesterday"
        if days < 30: return f"Last used: {days} days ago"
        if days < 365: return f"Last used: {days // 30} month(s) ago"
        return f"Last used: {days // 365} year(s) ago"

    def _get_poetry_venv_dir(self) -> Path:
        system = platform.system()
        if system == "Windows":
            return Path.home() / "AppData" / "Local" / "pypoetry" / "Cache" / "virtualenvs"
        elif system == "Darwin":
            return Path.home() / "Library" / "Caches" / "pypoetry" / "virtualenvs"
        return Path.home() / ".cache" / "pypoetry" / "virtualenvs"
