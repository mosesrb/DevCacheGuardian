"""
RescanWorker — re-runs the scanner(s) that own a specific CacheItem and emits
the updated item (or None if it has disappeared / been fully cleaned).

This replaces the inline _RescanThread class-inside-a-method anti-pattern
that was in main_window._on_rescan_single.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from app.models import CacheItem

if TYPE_CHECKING:
    pass


class RescanWorker(QThread):
    done = Signal(object)   # Optional[CacheItem]

    def __init__(self, item: CacheItem, parent=None):
        super().__init__(parent)
        self._item      = item
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def __del__(self):
        try:
            self._cancelled = True
            if self.isRunning():
                self.wait(3000)
        except RuntimeError:
            pass

    def run(self):
        from app.scanners import ALL_SCANNERS

        # Match scanners by ecosystem only — not by id substring
        # (id matching caused ALL Python scanners to re-run for any Python item)
        eco          = self._item.ecosystem
        target_id    = self._item.id
        candidates   = [S for S in ALL_SCANNERS
                        if getattr(S, "ecosystem", None) == eco]

        for ScannerClass in candidates:
            if self._cancelled:
                break
            try:
                result = ScannerClass().scan()
                for found in result.items:
                    if found.id == target_id:
                        self.done.emit(found)
                        return
            except Exception as exc:
                from loguru import logger
                logger.warning(f"RescanWorker: {ScannerClass.__name__} failed: {exc}")

        self.done.emit(None)
