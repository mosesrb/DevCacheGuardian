"""
backup_service.py — Pre-deletion backup of flagged configuration files (v1)

Creates a timestamped backup of any files flagged by content_analyzer before
deletion.  Backups live in:

    ~/.devcache_guardian/backups/<timestamp>_<cache_name>/
        MANIFEST.json
        <relative_path_of_file>
        ...

The backup is purely additive — it never deletes existing backups.
Restore is manual (open the backup folder) or via the History → Backups tab.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from loguru import logger

from app.services.content_analyzer import ContentWarning


# Backup root — inside the app's data directory
BACKUP_ROOT = Path.home() / ".devcache_guardian" / "backups"


def backup_warnings(
    warnings: List[ContentWarning],
    cache_name: str,
    cache_path: str,
) -> tuple[bool, str]:
    """
    Back up all files listed in *warnings* to a timestamped directory.

    Returns (success: bool, backup_path: str).
    On failure: returns (False, error_message).
    """
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug  = _slug(cache_name)
    dest  = BACKUP_ROOT / f"{ts}_{slug}"

    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Could not create backup directory: {exc}"

    manifest = {
        "created_at":  datetime.now().isoformat(),
        "cache_name":  cache_name,
        "cache_path":  cache_path,
        "files":       [],
    }

    backed_up = 0
    for w in warnings:
        src = Path(w.file_path)
        if not src.exists():
            continue
        rel     = Path(w.relative)
        dst     = dest / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            backed_up += 1
            manifest["files"].append({
                "original":   w.file_path,
                "backup":     str(dst),
                "relative":   w.relative,
                "label":      w.label,
                "severity":   w.severity,
            })
            logger.info(f"Backed up: {src} → {dst}")
        except (OSError, PermissionError) as exc:
            logger.warning(f"Could not back up {src}: {exc}")
            manifest["files"].append({
                "original": w.file_path,
                "error":    str(exc),
            })

    try:
        (dest / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning(f"Could not write backup manifest: {exc}")

    if backed_up == 0:
        return False, "No files could be backed up (all missing or permission denied)"

    return True, str(dest)


def get_all_backups() -> list[dict]:
    """
    Return all backup manifest records, newest first.
    Used by the History → Backups tab.
    """
    if not BACKUP_ROOT.exists():
        return []

    results = []
    for entry in sorted(BACKUP_ROOT.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        manifest_path = entry / "MANIFEST.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["backup_dir"] = str(entry)
            data["file_count"] = len([f for f in data.get("files", []) if "error" not in f])
            results.append(data)
        except Exception:
            pass

    return results


def open_backup_folder(backup_dir: str):
    """Open the backup directory in the system file manager."""
    from app.utils import open_in_explorer
    open_in_explorer(backup_dir)


def _slug(name: str) -> str:
    """Convert a cache name to a filesystem-safe slug."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return safe[:40].strip("_")
