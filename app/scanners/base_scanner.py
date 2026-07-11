"""
base_scanner.py (v5)

Changes from v4:
  - get_dir_size() gains a `stop_event` parameter (threading.Event).
    When set, the walk aborts immediately and returns whatever has been
    accumulated so far — prevents TEMP or any other huge directory from
    hanging the scan indefinitely.
  - get_dir_size() gains a `max_files` guard (default 200 000 files).
    TEMP folders on busy Windows machines can have 500k+ tiny files;
    counting all of them adds nothing useful but costs 10-30 seconds.
    Once the limit is hit we stop walking and return the partial total.
  - Both limits are soft — the returned value is the best estimate we
    can produce within the budget, not an error.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
import os
import threading

from app.models import CacheItem, ScanResult


# Safety caps for get_dir_size
_DEFAULT_MAX_FILES  = 200_000   # stop counting after this many entries
_DEFAULT_TIMEOUT_S  = 8.0       # seconds before we return a partial total


def get_dir_size(
    path: str,
    stop_event: Optional[threading.Event] = None,
    max_files:  int   = _DEFAULT_MAX_FILES,
) -> int:
    """
    Fast iterative directory size using os.scandir.

    Will stop early and return a partial total if:
      - stop_event is set (external cancellation from ScanWorker)
      - more than `max_files` entries have been visited

    The return value is always non-negative; callers should treat it as
    a lower-bound estimate when the walk was cut short.
    """
    total      = 0
    file_count = 0
    p          = Path(path)

    if not p.exists():
        return 0
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0

    stack = [str(p)]
    while stack:
        # Check cancellation on every directory boundary (not every file,
        # to keep overhead low — a directory boundary is a natural pause)
        if stop_event is not None and stop_event.is_set():
            break
        if file_count >= max_files:
            break

        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if stop_event is not None and stop_event.is_set():
                        return total
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total      += entry.stat(follow_symlinks=False).st_size
                            file_count += 1
                            if file_count >= max_files:
                                break
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

    return total


def expand_path(path: str) -> str:
    return str(Path(os.path.expandvars(os.path.expanduser(path))))


class BaseScanner(ABC):
    name: str      = "Base Scanner"
    ecosystem: str = "System"
    icon: str      = "folder"

    # Subclasses that call get_dir_size should pass self._stop to it.
    # ScanWorker sets this event when the user cancels or a timeout fires.
    _stop: threading.Event = threading.Event()   # default no-op (never set)

    def set_stop_event(self, event: threading.Event) -> None:
        """Called by ScanWorker before scan() to wire up cancellation."""
        self._stop = event

    @abstractmethod
    def scan(self) -> ScanResult: ...

    def _make_result(self, items: List[CacheItem],
                     errors: List[str] = None) -> ScanResult:
        return ScanResult(items=items, errors=errors or [],
                          scanner_name=self.name)
