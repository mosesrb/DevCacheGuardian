"""
test_db.py — Tests for database layer (init, log, prune, growth deltas).

Loads app.database.db directly via importlib to avoid sys.modules pollution
from other test files that stub app.database as a flat module.
"""
import sys
import types
import sqlite3
import importlib.util as _ilu
from pathlib import Path
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Pre-stub everything db.py needs, BEFORE loading it ───────────────────────

# loguru
if "loguru" not in sys.modules:
    _log = types.ModuleType("loguru")
    _log.logger = MagicMock()
    sys.modules["loguru"] = _log

# app.models (full stub with all attrs db.py might reference)
if "app.models" not in sys.modules:
    _m = types.ModuleType("app.models")
    class _RL: SAFE="safe"; REVIEW="review"; DANGER="danger"
    _m.RiskLevel     = _RL
    _m.CacheItem     = object
    _m.ScanResult    = object
    _m.CleanupMethod = object
    sys.modules["app.models"] = _m

# app.utils
if "app.utils" not in sys.modules:
    _u = types.ModuleType("app.utils")
    _u.fmt_bytes = lambda b: f"{b}B"
    _u.is_path_component_match = lambda p, c: c in Path(p).parts
    sys.modules["app.utils"] = _u

# app.database.policies — must be pre-loaded with all symbols __init__.py imports
_pol = types.ModuleType("app.database.policies")
_pol.init_policy_table = lambda: None
_pol.get_all_policies  = lambda: []
_pol.upsert_policy     = lambda *a, **k: None
_pol.delete_policy     = lambda *a, **k: None
_pol.mark_policy_run   = lambda *a, **k: None
_pol.get_due_policies  = lambda: []
sys.modules["app.database.policies"] = _pol

# ── Load app.database.db directly, bypassing the package __init__ chain ───────
_db_spec = _ilu.spec_from_file_location(
    "app.database.db",
    str(ROOT / "app" / "database" / "db.py"),
)
_db_mod = _ilu.module_from_spec(_db_spec)
sys.modules["app.database.db"] = _db_mod
_db_spec.loader.exec_module(_db_mod)

# Expose module-level names for patching
DB_PATH_ATTR = "DB_PATH"


# ── Fixture: isolated SQLite DB per test ─────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Give each test its own fresh SQLite database file."""
    db_path = tmp_path / "test.db"

    @contextmanager
    def _conn_ctx():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    with (
        patch.object(_db_mod, DB_PATH_ATTR, db_path),
        patch.object(_db_mod, "get_connection", _conn_ctx),
    ):
        _db_mod.init_db()
        yield db_path


def _raw(db_path: Path) -> sqlite3.Connection:
    """Open a direct connection to the test DB for assertion queries."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestInitDb:
    def test_all_tables_created(self, isolated_db):
        conn = _raw(isolated_db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        for t in ("scan_history", "cleanup_history", "ignored_paths",
                  "preferences", "scan_item_snapshots"):
            assert t in tables, f"Missing table: {t}"

    def test_all_indexes_created(self, isolated_db):
        conn = _raw(isolated_db)
        indexes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        conn.close()
        for idx in ("idx_scan_history_scanned_at",
                    "idx_cleanup_history_cleaned_at",
                    "idx_cleanup_history_cache_id",
                    "idx_scan_item_snapshots_scan_id",
                    "idx_scan_item_snapshots_cache_id"):
            assert idx in indexes, f"Missing index: {idx}"

    def test_default_preferences_seeded(self, isolated_db):
        conn = _raw(isolated_db)
        prefs = dict(conn.execute(
            "SELECT key, value FROM preferences"
        ).fetchall())
        conn.close()
        assert "scan_on_startup" in prefs
        assert "theme" in prefs
        assert "show_status_bar" in prefs

    def test_idempotent_safe_to_call_twice(self, isolated_db):
        _db_mod.init_db()  # second call must not raise or duplicate rows


class TestLogScan:
    def test_inserts_row(self, isolated_db):
        _db_mod.log_scan(1_000_000, 5, 3.2)
        conn = _raw(isolated_db)
        row = conn.execute(
            "SELECT total_bytes, item_count, duration_seconds FROM scan_history"
        ).fetchone()
        conn.close()
        assert row["total_bytes"] == 1_000_000
        assert row["item_count"]  == 5
        assert abs(row["duration_seconds"] - 3.2) < 0.01

    def test_multiple_scans_accumulate(self, isolated_db):
        _db_mod.log_scan(100, 1, 1.0)
        _db_mod.log_scan(200, 2, 2.0)
        conn = _raw(isolated_db)
        count = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
        conn.close()
        assert count >= 2

    def test_prune_runs_without_error(self, isolated_db):
        """log_scan triggers prune_old_snapshots — should not raise."""
        _db_mod.log_scan(0, 0, 0)

    def test_old_scans_pruned(self, isolated_db):
        conn = _raw(isolated_db)
        conn.execute(
            "INSERT INTO scan_history (scanned_at, total_bytes, item_count, duration_seconds)"
            " VALUES (datetime('now','-91 days'), 0, 0, 0)"
        )
        old_id = conn.execute(
            "SELECT id FROM scan_history ORDER BY id"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO scan_item_snapshots (scan_id,cache_id,cache_name,ecosystem,size_bytes)"
            " VALUES (?,  'x','X','Python',1)", (old_id,)
        )
        conn.commit()
        conn.close()

        _db_mod.prune_old_snapshots(keep_days=90)

        conn = _raw(isolated_db)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM scan_history WHERE id=?", (old_id,)
        ).fetchone()[0]
        conn.close()
        assert remaining == 0


class TestLogScanItems:
    def _latest_scan_id(self, db_path):
        conn = _raw(db_path)
        row = conn.execute(
            "SELECT id FROM scan_history ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else None

    def test_items_persisted(self, isolated_db):
        _db_mod.log_scan(0, 1, 0)
        sid = self._latest_scan_id(isolated_db)
        _db_mod.log_scan_items(sid, [
            {"cache_id": "pip",  "cache_name": "pip cache",
             "ecosystem": "Python", "size_bytes": 512_000},
            {"cache_id": "npm",  "cache_name": "npm cache",
             "ecosystem": "Node",   "size_bytes": 1_024_000},
        ])
        conn = _raw(isolated_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM scan_item_snapshots WHERE scan_id=?", (sid,)
        ).fetchone()[0]
        conn.close()
        assert count == 2

    def test_empty_list_no_error(self, isolated_db):
        _db_mod.log_scan(0, 0, 0)
        sid = self._latest_scan_id(isolated_db)
        _db_mod.log_scan_items(sid, [])


class TestIgnoredPaths:
    def test_add_and_retrieve(self, isolated_db):
        _db_mod.add_ignored_path("/home/user/project", "protect my work")
        paths = _db_mod.get_ignored_paths()
        assert "/home/user/project" in paths

    def test_remove_path(self, isolated_db):
        _db_mod.add_ignored_path("/home/user/tmp_project", "test")
        _db_mod.remove_ignored_path("/home/user/tmp_project")
        paths = _db_mod.get_ignored_paths()
        assert "/home/user/tmp_project" not in paths

    def test_duplicate_add_no_error(self, isolated_db):
        _db_mod.add_ignored_path("/home/user/dupe", "test")
        _db_mod.add_ignored_path("/home/user/dupe", "test again")  # UNIQUE constraint

    def test_empty_list_initially(self, isolated_db):
        paths = _db_mod.get_ignored_paths()
        assert isinstance(paths, list)


class TestPreferences:
    def test_set_and_get(self, isolated_db):
        _db_mod.set_preference("theme", "dark")
        assert _db_mod.get_preference("theme", "system") == "dark"

    def test_default_when_missing(self, isolated_db):
        val = _db_mod.get_preference("nonexistent_key_xyz", "my_default")
        assert val == "my_default"

    def test_overwrite(self, isolated_db):
        _db_mod.set_preference("theme", "light")
        _db_mod.set_preference("theme", "dark")
        assert _db_mod.get_preference("theme", "system") == "dark"

    def test_seeded_defaults_accessible(self, isolated_db):
        # init_db seeds scan_on_startup = 'true'
        val = _db_mod.get_preference("scan_on_startup", "false")
        assert val == "true"


class TestLogCleanup:
    def test_cleanup_logged(self, isolated_db):
        _db_mod.log_cleanup(
            "pip_cache", "pip cache", 1_000_000,
            "command", "pip cache purge", True, None
        )
        conn = _raw(isolated_db)
        row = conn.execute(
            "SELECT cache_id, bytes_reclaimed, success FROM cleanup_history"
        ).fetchone()
        conn.close()
        assert row["cache_id"]       == "pip_cache"
        assert row["bytes_reclaimed"]== 1_000_000
        assert row["success"]        == 1

    def test_failed_cleanup_logged(self, isolated_db):
        _db_mod.log_cleanup(
            "npm_cache", "npm cache", 0,
            "command", "npm cache clean", False, "Permission denied"
        )
        conn = _raw(isolated_db)
        row = conn.execute(
            "SELECT success, error_message FROM cleanup_history"
        ).fetchone()
        conn.close()
        assert row["success"] == 0
        assert "Permission" in row["error_message"]

    def test_get_cleanup_stats_totals(self, isolated_db):
        _db_mod.log_cleanup("a", "A", 500_000, "command", "cmd", True,  None)
        _db_mod.log_cleanup("b", "B", 300_000, "command", "cmd", False, "err")
        stats = _db_mod.get_cleanup_stats()
        assert stats["ops"]         >= 2
        assert stats["total_bytes"] >= 500_000

    def test_get_cleanup_history_returns_list(self, isolated_db):
        _db_mod.log_cleanup("x", "X", 0, "command", "cmd", True, None)
        history = _db_mod.get_cleanup_history(limit=50)
        assert isinstance(history, list)
        assert len(history) >= 1
