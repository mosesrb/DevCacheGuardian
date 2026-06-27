"""
test_cleaner_safety.py

Unit tests for CleanerService safety gates.
Run with:  pytest tests/test_cleaner_safety.py -v

These tests never write to disk — dry_run=True throughout.
"""
import os
import sys
import types
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Minimal stubs so CleanerService can be imported without Qt / loguru ───────

sys.modules.setdefault("PySide6", MagicMock())
sys.modules.setdefault("PySide6.QtCore", MagicMock())

_loguru = types.ModuleType("loguru")
_loguru.logger = MagicMock()
sys.modules["loguru"] = _loguru

_fake_db = types.ModuleType("app.database")
_fake_db.log_cleanup       = lambda *a, **k: None
_fake_db.get_ignored_paths = lambda: []
if "app.database" not in sys.modules:
    sys.modules["app.database"] = _fake_db

_m = types.ModuleType("app.models")
class _RL:
    SAFE = "safe"; REVIEW = "review"; DANGER = "danger"
class _CM:
    COMMAND = "command"; DIRECTORY = "directory"; NONE = "none"
class _CacheItem:
    def __init__(self, **kw): self.__dict__.update(kw)
_m.RiskLevel = _RL
_m.CleanupMethod = _CM
_m.CacheItem = _CacheItem
sys.modules["app.models"] = _m

_u = types.ModuleType("app.utils")
_u.fmt_bytes = lambda b: f"{b}B"
_u.is_path_component_match = lambda path, comp: comp in Path(path).parts
sys.modules["app.utils"] = _u

from app.cleaners.cleaner_service import CleanerService

HOME = Path.home().resolve()
TMP  = Path(tempfile.gettempdir()).resolve()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _svc(ignored=None) -> CleanerService:
    svc = CleanerService(dry_run=True)
    svc._ignored_paths = set(ignored or [])
    return svc

def is_blocked(path: str, ignored=None) -> bool:
    blocked, _ = _svc(ignored)._check_blocked(path)
    return blocked

def block_reason(path: str, ignored=None) -> str:
    _, reason = _svc(ignored)._check_blocked(path)
    return reason

def _item(**kw):
    defaults = dict(
        id="test", name="Test Cache", ecosystem="Python",
        path=str(HOME / "cache"), size_bytes=1_000_000,
        risk_level=_RL.SAFE, description="", long_description="",
        cleanup_method=_CM.DIRECTORY, cleanup_command=None,
    )
    defaults.update(kw)
    return _CacheItem(**defaults)


# ── Home-root guard ───────────────────────────────────────────────────────────

class TestHomeRootGuard:
    def test_home_root_blocked(self):
        assert is_blocked(str(HOME))

    def test_home_parent_blocked(self):
        assert is_blocked(str(HOME.parent))

    @pytest.mark.skipif(os.name == "nt", reason="Unix only")
    def test_filesystem_root_blocked(self):
        assert is_blocked("/")

    def test_cache_dir_inside_home_allowed(self, tmp_path):
        # A real subdirectory of tmp is allowed (not home root)
        assert not is_blocked(str(tmp_path))


# ── Protected path components ─────────────────────────────────────────────────

class TestProtectedComponents:
    @pytest.mark.parametrize("component", [
        ".git", ".ssh", "Documents", "Desktop", "Downloads",
        "Pictures", "Music", "Videos",
    ])
    def test_protected_component_blocked(self, component):
        p = str(HOME / "myproject" / component / "subdir")
        assert is_blocked(p), f"Expected {component} to be blocked"

    def test_documents_backup_not_blocked(self):
        """Whole-component match — 'Documents_backup' must NOT be blocked."""
        p = str(HOME / "Documents_backup" / "npm")
        assert not is_blocked(p)

    def test_git_suffix_not_blocked(self):
        """'.git' only blocks the exact component, not 'myrepo.git'."""
        p = str(HOME / "repos" / "myrepo.git" / "cache")
        assert not is_blocked(p)

    def test_nested_protected_still_blocked(self):
        p = str(HOME / "work" / ".ssh" / "npm" / "cache")
        assert is_blocked(p)


# ── Relative / traversal bypass ───────────────────────────────────────────────

class TestTraversalBypass:
    def test_dotdot_to_ssh_is_blocked(self):
        """HOME/cache/../.ssh must resolve to HOME/.ssh which is blocked."""
        evil = str(HOME / "cache" / ".." / ".ssh")
        assert is_blocked(evil)

    def test_dotdot_to_home_root_is_blocked(self):
        evil = str(HOME / "subdir" / ".." / ".." / HOME.name)
        # After resolve() this points at HOME or above — both blocked
        assert is_blocked(evil)

    def test_crafted_path_does_not_crash(self):
        """No path string should raise an unhandled exception."""
        evil = "/nonexistent/../../../../etc/passwd"
        blocked, reason = _svc()._check_blocked(evil)
        assert isinstance(blocked, bool)
        assert isinstance(reason, str)


# ── Symlink attacks ───────────────────────────────────────────────────────────

class TestSymlinkAttacks:
    def test_symlink_pointing_to_home_blocked(self, tmp_path):
        link = tmp_path / "evil_link"
        link.symlink_to(HOME)
        assert is_blocked(str(link))

    def test_symlink_pointing_to_parent_blocked(self, tmp_path):
        link = tmp_path / "evil_link2"
        link.symlink_to(HOME.parent)
        assert is_blocked(str(link))

    @pytest.mark.skipif(not (Path.home() / ".ssh").exists(),
                        reason=".ssh not present")
    def test_symlink_pointing_to_ssh_blocked(self, tmp_path):
        link = tmp_path / "cache_link"
        link.symlink_to(HOME / ".ssh")
        assert is_blocked(str(link))

    def test_benign_symlink_inside_tmp_not_blocked(self, tmp_path):
        """A symlink that resolves inside /tmp should not be blocked."""
        real_dir = tmp_path / "real_cache"
        real_dir.mkdir()
        link = tmp_path / "link_to_cache"
        link.symlink_to(real_dir)
        # tmp_path is under TMP — should be permitted
        assert not is_blocked(str(link))


# ── User-defined ignored paths ────────────────────────────────────────────────

class TestUserIgnoredPaths:
    def test_exact_protected_path_blocked(self, tmp_path):
        protected = (tmp_path / "my_project").resolve()
        protected.mkdir()
        child = str(protected / "node_modules" / ".cache")
        assert is_blocked(child, ignored={protected})

    def test_reason_mentions_user_protected(self, tmp_path):
        protected = (tmp_path / "proj").resolve()
        protected.mkdir()
        reason = block_reason(str(protected / "dist"), ignored={protected})
        assert "user-protected" in reason

    def test_sibling_not_blocked(self, tmp_path):
        protected = (tmp_path / "proj_a").resolve()
        protected.mkdir()
        sibling   = tmp_path / "proj_b"
        sibling.mkdir()
        assert not is_blocked(str(sibling / "cache"), ignored={protected})

    def test_parent_of_protected_not_blocked(self, tmp_path):
        """Protecting a child should not block the parent."""
        child = (tmp_path / "project" / "src").resolve()
        child.mkdir(parents=True)
        parent = tmp_path  # not the protected path
        assert not is_blocked(str(parent), ignored={child})


# ── DANGER item hard-refusal ──────────────────────────────────────────────────

class TestDangerRefusal:
    def test_danger_item_always_refused(self):
        svc  = CleanerService(dry_run=True)
        svc._ignored_paths = set()
        itm  = _item(risk_level=_RL.DANGER)
        result = svc.clean(itm)
        assert not result.success
        assert result.bytes_reclaimed == 0

    def test_danger_message_explains_reason(self):
        svc = CleanerService(dry_run=True)
        svc._ignored_paths = set()
        result = svc.clean(_item(risk_level=_RL.DANGER))
        msg = result.message.lower()
        assert "danger" in msg or "refused" in msg or "cannot" in msg

    def test_review_item_dry_run_succeeds(self):
        """REVIEW items should be processable in dry_run."""
        svc = CleanerService(dry_run=True)
        svc._ignored_paths = set()
        itm = _item(
            risk_level=_RL.REVIEW,
            path=str(TMP / "test_review_cache"),
        )
        # dry_run on a non-existent path should return a safe result or
        # graceful failure — never crash
        result = svc.clean(itm)
        assert isinstance(result.success, bool)


# ── Fail-safe exception handling ──────────────────────────────────────────────

class TestFailSafe:
    def test_outside_home_and_tmp_blocked(self):
        """An absolute path outside home/tmp must be blocked."""
        if os.name == "nt":
            pytest.skip("Unix path test")
        assert is_blocked("/usr/local/lib/python3.12")

    def test_etc_passwd_blocked(self):
        if os.name == "nt":
            pytest.skip("Unix path test")
        assert is_blocked("/etc/passwd")

    def test_dev_null_blocked(self):
        if os.name == "nt":
            pytest.skip("Unix path test")
        assert is_blocked("/dev/null")


# ── CleanResult type safety ───────────────────────────────────────────────────

class TestCleanResult:
    def test_bytes_reclaimed_is_float(self):
        from app.cleaners.cleaner_service import CleanResult
        r = CleanResult(success=True, bytes_reclaimed=17_179_869_184.0,
                        message="ok")
        assert isinstance(r.bytes_reclaimed, float)

    def test_large_value_no_overflow(self):
        from app.cleaners.cleaner_service import CleanResult
        large = 50 * 1024**3   # 50 GB as float
        r = CleanResult(success=True, bytes_reclaimed=float(large), message="ok")
        assert r.bytes_reclaimed == float(large)
