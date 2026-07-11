"""
conftest.py — Shared pytest setup for DevCache Guardian tests.

Runs before any test module is imported.  We build minimal stubs for the
heavy dependencies (PySide6, loguru, app.models, app.utils) here so that:

1. Tests that import directly from sub-modules work without Qt.
2. Stubs from one test file don't corrupt the sys.modules namespace
   seen by other test files.

Each individual test file may EXTEND these stubs but should never
remove them, to avoid import-order-dependent failures.
"""
import sys
import os
import types
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ── PySide6 — all known submodules ───────────────────────────────────────────
_pyside6_mock = MagicMock()
_pyside6_mock.__version__ = "6.0.0"
_pyside6_mock.QtCore.qVersion.return_value = "6.0.0"
_pyside6_mock.QtCore.__version__ = "6.0.0"
for _mod_name in [
    "PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
    "PySide6.QtCharts", "PySide6.QtSvg", "PySide6.QtOpenGL",
]:
    sys.modules.setdefault(_mod_name, _pyside6_mock)

# ── loguru ────────────────────────────────────────────────────────────────────
if "loguru" not in sys.modules:
    _loguru = types.ModuleType("loguru")
    _loguru.logger = MagicMock()
    sys.modules["loguru"] = _loguru

# ── app.models ────────────────────────────────────────────────────────────────
# Only install the stub if the real package hasn't been imported yet.
# test_db.py imports the real app.database which in turn imports real app.models.
# We must not let a thin stub shadow the real package for those tests.
# Solution: install a REAL-LOOKING stub that satisfies isinstance checks.
if "app.models" not in sys.modules:
    _models = types.ModuleType("app.models")
    class _RiskLevel:
        SAFE = "safe"; REVIEW = "review"; DANGER = "danger"
    class _CleanupMethod:
        COMMAND = "command"; DIRECTORY = "directory"; NONE = "none"
    class _CacheItem:
        def __init__(self, **kw): self.__dict__.update(kw)
    class _ScanResult:
        def __init__(self, items=None, errors=None, scanner_name=""):
            self.items = items or []; self.errors = errors or []
            self.scanner_name = scanner_name
        @property
        def total_bytes(self): return sum(i.size_bytes for i in self.items)
        @property
        def item_count(self): return len(self.items)
    _models.RiskLevel    = _RiskLevel
    _models.CleanupMethod= _CleanupMethod
    _models.CacheItem    = _CacheItem
    _models.ScanResult   = _ScanResult
    sys.modules["app.models"] = _models
    # also register submodules so 'from .cache_item import ...' in base_scanner works
    _ci_mod = types.ModuleType("app.models.cache_item")
    _ci_mod.CacheItem     = _CacheItem
    _ci_mod.RiskLevel     = _RiskLevel
    _ci_mod.CleanupMethod = _CleanupMethod
    sys.modules["app.models.cache_item"] = _ci_mod
    _sr_mod = types.ModuleType("app.models.scan_result")
    _sr_mod.ScanResult = _ScanResult
    sys.modules["app.models.scan_result"] = _sr_mod

# ── app.utils ─────────────────────────────────────────────────────────────────
if "app.utils" not in sys.modules:
    from pathlib import Path as _Path
    _utils = types.ModuleType("app.utils")
    def _fmt(b):
        if b >= 1024**3: return f"{b/1024**3:.1f} GB"
        if b >= 1024**2: return f"{b/1024**2:.1f} MB"
        return f"{b} B"
    _utils.fmt_bytes = _fmt
    _utils.is_path_component_match = lambda p, c: c in _Path(p).parts
    sys.modules["app.utils"] = _utils

# ── app.database.policies (always stub for non-db tests) ─────────────────────
# app/database/__init__.py imports these names from policies — the stub must
# export all of them or the real __init__.py will raise ImportError when
# test_db.py triggers the real package import.
if "app.database.policies" not in sys.modules:
    _pol = types.ModuleType("app.database.policies")
    _pol.init_policy_table = lambda: None
    _pol.get_all_policies  = lambda: []
    _pol.upsert_policy     = lambda *a, **k: None
    _pol.delete_policy     = lambda *a, **k: None
    _pol.mark_policy_run   = lambda *a, **k: None
    _pol.get_due_policies  = lambda: []
    sys.modules["app.database.policies"] = _pol

# Make project root importable
import pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).parent.parent))
