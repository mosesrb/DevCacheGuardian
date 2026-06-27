"""
app/utils.py — shared utilities used across the codebase.

Centralises _fmt (was duplicated in 4 files) and path safety helpers.
"""
from __future__ import annotations

from pathlib import Path


def fmt_bytes(b: int) -> str:
    """Human-readable byte size string."""
    if b >= 1024 ** 3: return f"{b / 1024 ** 3:.2f} GB"
    if b >= 1024 ** 2: return f"{b / 1024 ** 2:.1f} MB"
    if b >= 1024:      return f"{b / 1024:.0f} KB"
    return f"{b} B"


def is_path_component_match(path: str, protected_name: str) -> bool:
    """
    Return True only if `protected_name` matches a *whole path component*,
    not a substring.

    Examples
    --------
    is_path_component_match("/home/user/.ssh/keys", ".ssh")   → True
    is_path_component_match("/home/user/Documents", "Documents") → True
    is_path_component_match("/cache/Documents_backup", "Documents") → False  ← fixed
    """
    p = Path(path)
    name_lower = protected_name.lower().replace("/", "").replace("\\", "")
    for part in p.parts:
        if part.lower() == name_lower:
            return True
    return False


import platform
import sys


def get_platform() -> str:
    """Returns 'windows', 'macos', or 'linux'."""
    s = platform.system().lower()
    if s == "darwin": return "macos"
    if s == "windows": return "windows"
    return "linux"


def open_in_explorer(path: str) -> str | None:
    """
    Open *path* in the system file manager.
    Returns None on success, or an error string if the path doesn't exist
    or the file manager can't be launched.
    """
    import subprocess
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return f"Path no longer exists: {path}"
    target = str(p) if p.is_dir() else str(p.parent)
    plt = get_platform()
    try:
        if plt == "windows":
            subprocess.Popen(["explorer", target])
        elif plt == "macos":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return None
    except Exception as exc:
        return str(exc)


def copy_to_clipboard(text: str):
    """Copy text to the system clipboard via Qt."""
    from PySide6.QtWidgets import QApplication
    cb = QApplication.clipboard()
    if cb:
        cb.setText(text)
