"""
test_scoring.py — Isolated unit tests for the health-score algorithm.

Imports scoring.py directly by file path so we don't pull in the full
services package (and therefore don't need Qt, loguru, or all scanners).
"""
import sys
import types
import importlib.util as _ilu
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Stub app.models BEFORE loading scoring.py ─────────────────────────────────
class _RL:
    SAFE = "safe"; REVIEW = "review"; DANGER = "danger"

class _CacheItem:
    def __init__(self, size, risk=_RL.SAFE):
        self.size_bytes = size
        self.risk_level = risk

_m = types.ModuleType("app.models")
_m.RiskLevel   = _RL
_m.CacheItem   = _CacheItem
_m.CleanupMethod = object()
_m.ScanResult  = object()
sys.modules["app.models"] = _m

_u = types.ModuleType("app.utils")
def _fmtb(b):
    if b >= 1024**3: return f"{b/1024**3:.1f} GB"
    if b >= 1024**2: return f"{b/1024**2:.1f} MB"
    return f"{b} B"
_u.fmt_bytes = _fmtb
_u.is_path_component_match = lambda p, c: c in Path(p).parts
sys.modules["app.utils"] = _u

# ── Load scoring.py directly, bypassing services/__init__ ────────────────────
_spec = _ilu.spec_from_file_location(
    "app.services.scoring",
    str(ROOT / "app" / "services" / "scoring.py"),
)
_mod = _ilu.module_from_spec(_spec)
sys.modules["app.services.scoring"] = _mod
_spec.loader.exec_module(_mod)
get_health_score = _mod.get_health_score


# ── Helpers ───────────────────────────────────────────────────────────────────

def item(size_bytes, risk=_RL.SAFE):
    return _CacheItem(size_bytes, risk)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGetHealthScore:
    def test_empty_list_is_perfect(self):
        r = get_health_score([])
        assert r["score"] == 100
        assert r["grade"] == "A"
        assert r["breakdown"] == {}

    def test_small_safe_cache_stays_A(self):
        r = get_health_score([item(200 * 1024**2)])  # 200 MB
        assert r["grade"] == "A"
        assert r["score"] >= 90

    def test_large_safe_cache_lowers_score(self):
        # 8 GB safe → deduct min(40, 8×4)=32 → score=68 → C
        r = get_health_score([item(8 * 1024**3)])
        assert r["score"] == 68
        assert r["grade"] == "C"

    def test_safe_deduction_capped_at_40(self):
        r = get_health_score([item(100 * 1024**3)])
        assert r["score"] == 60

    def test_review_smaller_deduction_than_safe(self):
        r_safe   = get_health_score([item(1024**3, _RL.SAFE)])
        r_review = get_health_score([item(1024**3, _RL.REVIEW)])
        assert r_review["score"] > r_safe["score"]

    def test_review_deduction_capped_at_20(self):
        r = get_health_score([item(100 * 1024**3, _RL.REVIEW)])
        assert r["score"] == 80

    def test_danger_items_not_penalised(self):
        a = get_health_score([item(1024**3, _RL.SAFE)])
        b = get_health_score([item(1024**3, _RL.SAFE),
                              item(50 * 1024**3, _RL.DANGER)])
        assert a["score"] == b["score"]

    def test_combined_deduction_never_below_zero(self):
        r = get_health_score([item(200 * 1024**3, _RL.SAFE),
                              item(200 * 1024**3, _RL.REVIEW)])
        assert r["score"] >= 0

    def test_breakdown_keys_present(self):
        r = get_health_score([item(512 * 1024**2)])
        assert set(r["breakdown"]) == {
            "safe_reclaimable", "needs_review", "total_found"
        }

    def test_grade_a_boundary(self):
        # 2.5 GB → deduct 10 → score 90 → A
        r = get_health_score([item(int(2.5 * 1024**3))])
        assert r["score"] == 90
        assert r["grade"] == "A"

    def test_grade_b(self):
        # 4 GB → deduct 16 → score 84 → B
        r = get_health_score([item(4 * 1024**3)])
        assert r["grade"] == "B"

    def test_grade_d_boundary(self):
        # 20 GB safe (cap -40) + 20 GB review (cap -20) → score 40 → D
        r = get_health_score([item(20 * 1024**3, _RL.SAFE),
                              item(20 * 1024**3, _RL.REVIEW)])
        assert r["score"] == 40
        assert r["grade"] == "D"

    def test_multiple_items_summed(self):
        r = get_health_score([item(5 * 1024**3), item(5 * 1024**3)])
        assert r["score"] == 60  # 10 GB → -40

    def test_return_types(self):
        r = get_health_score([])
        assert isinstance(r["score"], int)
        assert isinstance(r["grade"], str)
        assert isinstance(r["breakdown"], dict)
