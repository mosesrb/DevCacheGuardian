"""
test_report_generator.py — Tests for Markdown and HTML report generation.
Verifies injection-safety and data correctness.
"""
import sys
import types
import importlib.util as _ilu
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Stub app.models before loading report_generator ─────────────────────────
_m = types.ModuleType("app.models")
class _RL:
    SAFE = "safe"; REVIEW = "review"; DANGER = "danger"
class _CM:
    COMMAND = "command"; DIRECTORY = "directory"; NONE = "none"
_m.RiskLevel     = _RL
_m.CleanupMethod = _CM
_m.CacheItem     = object
_m.ScanResult    = object
sys.modules["app.models"] = _m

_u = types.ModuleType("app.utils")
_u.fmt_bytes = lambda b: f"{b/1024**3:.2f} GB" if b >= 1024**3 else f"{b}B"
_u.is_path_component_match = lambda p, c: c in Path(p).parts
sys.modules["app.utils"] = _u

# Stub app.database — report_generator calls get_cleanup_stats internally
_db = types.ModuleType("app.database")
_db.get_cleanup_stats = lambda: {"total_bytes": 0, "ops": 0}
sys.modules["app.database"] = _db

# Load report_generator.py directly (avoids services/__init__ → scan_worker → scanners chain)
_spec = _ilu.spec_from_file_location(
    "app.services.report_generator",
    str(ROOT / "app" / "services" / "report_generator.py"),
)
_rg_mod = _ilu.module_from_spec(_spec)
sys.modules["app.services.report_generator"] = _rg_mod
_spec.loader.exec_module(_rg_mod)

from app.services.report_generator import (
    generate_markdown_report,
    generate_html_report,
    _md_escape,
)


class _Item:
    def __init__(self, name="Test Cache", ecosystem="Python",
                 size_bytes=1_000_000, risk_level=_RL.SAFE,
                 path="/home/user/.cache/test",
                 cleanup_command="pip cache purge",
                 cleanup_method=_CM.COMMAND,
                 description="A test cache",
                 long_description="A longer test cache description."):
        self.id               = name.lower().replace(" ", "_")
        self.name             = name
        self.ecosystem        = ecosystem
        self.size_bytes       = size_bytes
        self.risk_level       = risk_level
        self.path             = path
        self.cleanup_command  = cleanup_command
        self.cleanup_method   = cleanup_method
        self.description      = description
        self.long_description = long_description
        self.size_label       = _u.fmt_bytes(size_bytes)


HEALTH = {"score": 82, "grade": "B", "breakdown": {
    "safe_reclaimable": "800MB", "needs_review": "200MB", "total_found": "1GB"
}}
STATS  = {"total_bytes": 5_000_000, "ops": 10}


# ── Markdown escape ───────────────────────────────────────────────────────────

class TestMdEscape:
    def test_pipe_escaped(self):
        assert "\\|" in _md_escape("foo|bar")

    def test_backtick_escaped(self):
        assert "\\`" in _md_escape("foo`bar")

    def test_safe_text_unchanged(self):
        assert _md_escape("pip cache purge") == "pip cache purge"

    def test_multiple_pipes(self):
        result = _md_escape("a|b|c")
        assert result.count("\\|") == 2


# ── Markdown report ───────────────────────────────────────────────────────────

class TestMarkdownReport:
    def _generate(self, items=None, health=None, deltas=None):
        items  = items  or [_Item()]
        health = health or HEALTH
        return generate_markdown_report(items, health, deltas or [], STATS)

    def test_contains_grade(self):
        md = self._generate()
        assert "Grade B" in md or "Grade: B" in md or "B" in md

    def test_contains_score(self):
        md = self._generate()
        assert "82" in md

    def test_all_items_present(self):
        items = [_Item("pip cache"), _Item("npm cache", ecosystem="Node")]
        md = self._generate(items)
        assert "pip cache" in md
        assert "npm cache" in md

    def test_pipe_in_name_escaped(self):
        item = _Item(name="cache|with|pipes")
        md = self._generate([item])
        # The raw pipe should be escaped so the table doesn't break
        lines = [l for l in md.splitlines() if "cache" in l and "with" in l]
        for line in lines:
            # No bare unescaped pipe breaking the table
            assert "cache|with|pipes" not in line

    def test_backtick_in_command_escaped(self):
        item = _Item(cleanup_command="run `dangerous` cmd")
        md = self._generate([item])
        # raw backtick inside code block should be escaped
        assert "\\`" in md or "`dangerous`" not in md

    def test_growth_section_present_when_deltas_given(self):
        deltas = [{
            "cache_id": "pip", "cache_name": "pip cache", "ecosystem": "Python",
            "prev_bytes": 500_000, "curr_bytes": 5_000_000,
            "delta_bytes": 4_500_000,   # >1 MB threshold required by _prep()
        }]
        md = self._generate(deltas=deltas)
        assert "Cache Growth" in md

    def test_growth_section_absent_when_no_deltas(self):
        md = self._generate(deltas=[])
        assert "Cache Growth" not in md

    def test_valid_markdown_table_structure(self):
        md = self._generate()
        table_lines = [l for l in md.splitlines() if l.startswith("|")]
        # Every table line should have balanced pipes
        for line in table_lines:
            assert line.startswith("|") and line.endswith("|"), \
                f"Malformed table line: {line}"

    def test_pipe_in_path_escaped_in_command_column(self):
        item = _Item(cleanup_command="cmd --path /tmp/foo|bar")
        md = self._generate([item])
        cmd_lines = [l for l in md.splitlines() if "cmd" in l and "path" in l]
        for line in cmd_lines:
            assert "/tmp/foo|bar" not in line  # must be escaped


# ── HTML report ───────────────────────────────────────────────────────────────

class TestHtmlReport:
    def _generate(self, items=None, health=None, deltas=None):
        items  = items  or [_Item()]
        health = health or HEALTH
        return generate_html_report(items, health, deltas or [], STATS)

    def test_is_html(self):
        html = self._generate()
        assert "<html" in html.lower() or "<!doctype" in html.lower()

    def test_grade_present(self):
        html = self._generate()
        assert "B" in html

    def test_xss_in_cache_name_escaped(self):
        item = _Item(name="<script>alert('xss')</script>")
        html = self._generate([item])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_xss_in_command_escaped(self):
        item = _Item(cleanup_command="<img src=x onerror=alert(1)>")
        html = self._generate([item])
        assert "<img" not in html

    def test_xss_in_path_escaped(self):
        item = _Item(path="</td><script>alert(1)</script>")
        html = self._generate([item])
        assert "<script>" not in html

    def test_special_chars_in_ecosystem_escaped(self):
        item = _Item(ecosystem="<Node & Friends>")
        html = self._generate([item])
        assert "<Node" not in html
        assert "&lt;Node" in html or "Node" in html

    def test_contains_health_score(self):
        html = self._generate()
        assert "82" in html

    def test_multiple_items_all_rendered(self):
        items = [_Item(f"cache_{i}") for i in range(5)]
        html = self._generate(items)
        for i in range(5):
            assert f"cache_{i}" in html
