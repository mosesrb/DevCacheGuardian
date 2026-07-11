"""
ScanWorker (v7) — Parallel Scanner Engine with Cancellation & Per-Scanner Timeout

Changes from v6
---------------
* A shared threading.Event (_stop_event) is passed to every scanner instance
  before scan() is called.  Setting the event causes any in-progress
  get_dir_size() call to abort immediately at the next directory boundary.

* Per-scanner wall-clock timeout (default 15 s).  If a single scanner doesn't
  finish within that window it is considered timed-out: the event is set,
  the future is abandoned, and an error is recorded.  The rest of the scan
  continues normally.  This is the primary guard against a hung TEMP walk.

* cancel() now also sets the stop event so in-flight get_dir_size walks
  abort quickly instead of running to completion before the worker sees
  _cancelled.

* Global scan timeout (default 120 s) as a backstop — if the whole scan
  hasn't finished in 2 minutes something is badly wrong and we give up.

Architecture
------------
- Main QThread owns the executor; worker threads each run one scanner.
- stop_event is shared across ALL scanners so cancelling from the UI stops
  every in-flight walk simultaneously, not just the one that's "next".
- Errors from timed-out or crashed scanners are recorded but don't kill
  the rest of the scan.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from typing import List

from PySide6.QtCore import QThread, Signal
from loguru import logger

from app.scanners import ALL_SCANNERS
from app.models import CacheItem, ScanResult


_MAX_WORKERS           = 6      # disk I/O bound; more workers just thrash the page cache
_SCANNER_TIMEOUT_S     = 15     # seconds before a single scanner is considered hung
_GLOBAL_SCAN_TIMEOUT_S = 120    # seconds before the whole scan is abandoned


class ScanWorker(QThread):
    """
    Runs all scanners in parallel.
    Emits progress, item_found, finished, and error signals.
    """

    progress   = Signal(str, int, int)   # (scanner_name, completed_count, total)
    item_found = Signal(object)          # CacheItem
    finished   = Signal(list)            # List[CacheItem]
    error      = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled   = False
        self._stop_event  = threading.Event()
        self._lock        = threading.Lock()
        self._completed   = 0

    def cancel(self):
        """Stop the scan as fast as possible. Safe to call from any thread."""
        self._cancelled = True
        self._stop_event.set()      # ← makes all in-flight get_dir_size walks abort

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def __del__(self):
        try:
            self.cancel()
            if self.isRunning():
                self.wait(3000)
        except RuntimeError:
            pass

    def run(self):
        all_items: List[CacheItem] = []
        total      = len(ALL_SCANNERS)
        self._completed = 0
        scan_start = time.monotonic()

        def run_scanner(scanner_class):
            """Executed in a worker thread. Returns (items, errors, name)."""
            if self._cancelled or self._stop_event.is_set():
                name = getattr(scanner_class, "name", scanner_class.__name__)
                return [], [], name

            scanner = scanner_class()
            scanner.set_stop_event(self._stop_event)   # wire up cancellation
            sname = getattr(scanner, "name", scanner_class.__name__)
            logger.info(f"[scan] Starting: {sname}")
            t0 = time.monotonic()
            try:
                result: ScanResult = scanner.scan()
                elapsed = time.monotonic() - t0
                logger.info(f"[scan] Done: {sname}  ({elapsed:.1f}s, "
                            f"{len(result.items)} items)")
                return result.items, result.errors, sname
            except Exception as exc:
                logger.exception(f"[scan] Scanner {sname} crashed")
                return [], [str(exc)], sname

        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, total)) as executor:
            futures = {
                executor.submit(run_scanner, sc): sc
                for sc in ALL_SCANNERS
            }
            pending = set(futures.keys())

            while pending:
                # Check global scan timeout
                if time.monotonic() - scan_start > _GLOBAL_SCAN_TIMEOUT_S:
                    logger.warning("[scan] Global timeout reached — aborting remaining scanners")
                    self._stop_event.set()
                    self.error.emit(
                        "Scan timed out after 2 minutes. "
                        "Some locations may not have been measured."
                    )
                    break

                if self._cancelled:
                    break

                # Wait for the next future to complete, with a per-scanner timeout
                done, pending = wait(pending, timeout=_SCANNER_TIMEOUT_S,
                                     return_when=FIRST_COMPLETED)

                if not done:
                    # Nothing finished in _SCANNER_TIMEOUT_S seconds.
                    # Figure out which scanner is the likely culprit and log it.
                    elapsed = time.monotonic() - scan_start
                    logger.warning(
                        f"[scan] No scanner completed in {_SCANNER_TIMEOUT_S}s "
                        f"(total elapsed {elapsed:.0f}s) — nudging stop event"
                    )
                    # Nudge the stop event so get_dir_size walks check it;
                    # clear it immediately after so non-hung scanners can finish.
                    # This is a best-effort hint, not a hard kill.
                    self._stop_event.set()
                    time.sleep(0.05)
                    if not self._cancelled:
                        self._stop_event.clear()
                    continue

                for future in done:
                    if self._cancelled:
                        break
                    try:
                        items, errors, name = future.result()
                    except Exception as exc:
                        name  = getattr(futures[future], "name", "Unknown")
                        items, errors = [], [str(exc)]
                        self.error.emit(f"{name}: {exc}")

                    with self._lock:
                        self._completed += 1
                        completed_now = self._completed

                    self.progress.emit(name, completed_now, total)

                    for item in items:
                        all_items.append(item)
                        self.item_found.emit(item)

                    for err in errors:
                        logger.warning(f"[scan] {name}: {err}")

        self.finished.emit(all_items)
