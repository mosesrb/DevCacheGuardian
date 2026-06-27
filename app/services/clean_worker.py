"""
CleanWorker (v8) — executes cleanup operations off the main thread.

Overflow fix
------------
Qt signals typed as Signal(int) are C++ `int` — signed 32-bit, max ~2.1 GB.
Large AI model caches (17 GB, 34 GB, etc.) overflowed silently with a
RuntimeWarning.

Fix: bytes_reclaimed is emitted as a Python float (Signal(float)) which Qt
maps to C++ double — 64-bit, handles up to 2^53 bytes (~8 PB) precisely.
The finished signal's total is likewise float.
All callers that previously received int now receive float; fmt_bytes() in
app/utils.py accepts both int and float so no other changes needed.
"""
from PySide6.QtCore import QThread, Signal
from typing import List, Tuple

from loguru import logger

from app.models import CacheItem
from app.cleaners.cleaner_service import CleanerService, CleanResult


class CleanWorker(QThread):

    progress  = Signal(str, int, int)             # (name, current, total)  — counts never overflow
    item_done = Signal(str, bool, float, str)     # (cache_id, success, bytes_reclaimed, message)
    finished  = Signal(float, list, list)         # (total_bytes, failures, results)

    def __init__(self, items: List[CacheItem], dry_run: bool = False, parent=None):
        super().__init__(parent)
        self._items     = list(items)
        self._dry_run   = dry_run
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

    # ── thread entry ─────────────────────────────────────────────────────────

    def run(self):
        service   = CleanerService(dry_run=self._dry_run)
        total     = len(self._items)
        reclaimed = 0.0          # float from the start — no overflow risk
        failures: List[str]                           = []
        results:  List[Tuple[CacheItem, CleanResult]] = []

        for idx, item in enumerate(self._items):
            if self._cancelled:
                break

            self.progress.emit(item.name, idx + 1, total)
            logger.info(
                f"{'[DRY RUN] ' if self._dry_run else ''}Processing: {item.name}"
            )

            try:
                result = service.clean(item)
            except Exception as exc:
                logger.exception(f"Unexpected error for {item.name}")
                result = CleanResult(
                    success=False, bytes_reclaimed=0,
                    message=str(exc), error=str(exc),
                    dry_run=self._dry_run,
                )

            # Emit as float to avoid Qt int32 overflow on large caches
            self.item_done.emit(
                item.id,
                result.success,
                float(result.bytes_reclaimed),
                result.message,
            )
            results.append((item, result))

            if result.success:
                reclaimed += float(result.bytes_reclaimed)
            else:
                failures.append(f"{item.name}: {result.message}")

        self.finished.emit(reclaimed, failures, results)
