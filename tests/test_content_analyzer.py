"""
test_content_analyzer.py — Tests for the pre-deletion content analysis system.

Runs fully headless — creates real temp directories to test filesystem walking.
"""
import sys
import json
import types
import shutil
import tempfile
import importlib.util as _ilu
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load content_analyzer directly (no app.services chain needed)
_spec = _ilu.spec_from_file_location(
    "app.services.content_analyzer",
    str(ROOT / "app" / "services" / "content_analyzer.py"),
)
_ca = _ilu.module_from_spec(_spec)
sys.modules["app.services.content_analyzer"] = _ca
_spec.loader.exec_module(_ca)

analyze_directory    = _ca.analyze_directory
ContentWarning       = _ca.ContentWarning
has_critical_warnings = _ca.has_critical_warnings
warnings_by_severity = _ca.warnings_by_severity
KNOWN_CONFIG_FILES   = _ca.KNOWN_CONFIG_FILES


# ── helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def cache_dir():
    """Temporary directory simulating a cache root. Cleaned up after each test."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


def make_file(root: Path, rel: str, content: str = "") -> Path:
    """Create a file at root/rel, making parent dirs as needed."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ── Empty / non-existent directory ───────────────────────────────────────────

class TestEmptyAndMissing:
    def test_empty_dir_no_warnings(self, cache_dir):
        assert analyze_directory(str(cache_dir), "gradle_cache") == []

    def test_nonexistent_path_no_warnings(self):
        assert analyze_directory("/nonexistent/path/xyz_123", "pip_cache") == []

    def test_file_path_no_warnings(self, cache_dir):
        f = make_file(cache_dir, "somefile.txt")
        assert analyze_directory(str(f), "pip_cache") == []


# ── Known config file registry ────────────────────────────────────────────────

class TestKnownConfigRegistry:
    def test_gradle_properties_flagged(self, cache_dir):
        make_file(cache_dir, "gradle.properties", "org.gradle.jvmargs=-Xmx2g")
        ws = analyze_directory(str(cache_dir), "gradle_cache")
        assert any("gradle.properties" in w.relative for w in ws)

    def test_gradle_properties_is_critical(self, cache_dir):
        make_file(cache_dir, "gradle.properties")
        ws = analyze_directory(str(cache_dir), "gradle_cache")
        matches = [w for w in ws if "gradle.properties" in w.relative]
        assert matches and matches[0].severity == "critical"

    def test_maven_settings_xml_flagged(self, cache_dir):
        make_file(cache_dir, "settings.xml", "<settings/>")
        ws = analyze_directory(str(cache_dir), "maven_cache")
        assert any("settings.xml" in w.relative for w in ws)

    def test_maven_settings_security_xml_flagged(self, cache_dir):
        make_file(cache_dir, "settings-security.xml")
        ws = analyze_directory(str(cache_dir), "maven_cache")
        assert any("settings-security.xml" in w.relative for w in ws)

    def test_cargo_credentials_toml_flagged(self, cache_dir):
        make_file(cache_dir, "credentials.toml", "[registry]\ntoken = 'abc'")
        ws = analyze_directory(str(cache_dir), "cargo_cache")
        assert any("credentials.toml" in w.relative for w in ws)
        assert ws[0].severity == "critical"

    def test_docker_config_json_flagged(self, cache_dir):
        make_file(cache_dir, "config.json", '{"auths":{}}')
        ws = analyze_directory(str(cache_dir), "docker_cache")
        assert any("config.json" in w.relative for w in ws)
        assert ws[0].severity == "critical"

    def test_huggingface_token_flagged(self, cache_dir):
        make_file(cache_dir, "token", "hf_abc123")
        ws = analyze_directory(str(cache_dir), "huggingface_cache")
        assert any(w.relative == "token" for w in ws)
        assert ws[0].severity == "critical"

    def test_android_debug_keystore_flagged(self, cache_dir):
        make_file(cache_dir, "debug.keystore")
        ws = analyze_directory(str(cache_dir), "android_cache")
        assert any("debug.keystore" in w.relative for w in ws)
        assert ws[0].severity == "critical"

    def test_nuget_config_flagged(self, cache_dir):
        make_file(cache_dir, "NuGet.Config")
        ws = analyze_directory(str(cache_dir), "nuget_cache")
        assert any("NuGet.Config" in w.relative for w in ws)


# ── Heuristic detection ───────────────────────────────────────────────────────

class TestHeuristicDetection:
    def test_token_file_flagged_for_unknown_tool(self, cache_dir):
        """'token' file should be caught by heuristic even without cache_id."""
        make_file(cache_dir, "token")
        ws = analyze_directory(str(cache_dir), "unknown_tool_xyz")
        assert any(w.relative == "token" for w in ws)

    def test_credentials_json_flagged(self, cache_dir):
        make_file(cache_dir, "credentials.json")
        ws = analyze_directory(str(cache_dir), "unknown_tool")
        assert any("credentials.json" in w.relative for w in ws)

    def test_pem_cert_at_root_flagged(self, cache_dir):
        make_file(cache_dir, "server.pem")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any(".pem" in w.relative for w in ws)
        assert ws[0].severity == "critical"

    def test_keystore_file_flagged(self, cache_dir):
        make_file(cache_dir, "release.keystore")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any(".keystore" in w.relative for w in ws)

    def test_jks_file_flagged(self, cache_dir):
        make_file(cache_dir, "release.jks")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any(".jks" in w.relative for w in ws)

    def test_private_key_flagged(self, cache_dir):
        make_file(cache_dir, "id_rsa")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any("id_rsa" in w.relative for w in ws)
        assert ws[0].severity == "critical"

    def test_ed25519_key_flagged(self, cache_dir):
        make_file(cache_dir, "id_ed25519")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any("id_ed25519" in w.relative for w in ws)

    def test_properties_file_at_root_flagged(self, cache_dir):
        make_file(cache_dir, "build.properties")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any(".properties" in w.relative for w in ws)

    def test_toml_at_root_flagged(self, cache_dir):
        make_file(cache_dir, "config.toml")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any(".toml" in w.relative for w in ws)

    def test_safe_artifact_jar_not_flagged(self, cache_dir):
        make_file(cache_dir, "guava-31.0.jar")
        ws = analyze_directory(str(cache_dir), "maven_cache")
        assert not any(".jar" in w.relative for w in ws)

    def test_pyc_not_flagged(self, cache_dir):
        make_file(cache_dir, "module.cpython-312.pyc")
        ws = analyze_directory(str(cache_dir), "pip_cache")
        assert ws == []

    def test_lock_file_not_flagged(self, cache_dir):
        make_file(cache_dir, "package-lock.json")
        ws = analyze_directory(str(cache_dir), "npm_cache")
        # lock files are in _SAFE_EXTENSIONS — should not be flagged
        assert not any("package-lock" in w.relative for w in ws)


# ── Depth limiting ────────────────────────────────────────────────────────────

class TestDepthLimiting:
    def test_config_at_depth_0_flagged(self, cache_dir):
        make_file(cache_dir, "config.toml")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any("config.toml" in w.relative for w in ws)

    def test_toml_at_depth_2_not_flagged_by_extension(self, cache_dir):
        """TOML extension heuristic only fires at depth 0; deep toml files are build artifacts."""
        make_file(cache_dir, "packages/foo/build.toml")
        ws = analyze_directory(str(cache_dir), "cargo_cache")
        # The heuristic extension check only fires at depth 0
        extension_matches = [w for w in ws if w.relative == "packages/foo/build.toml"]
        assert not extension_matches

    def test_critical_cert_at_depth_1_still_flagged(self, cache_dir):
        """PEM files are critical regardless of depth (caught at depth ≤ 1)."""
        make_file(cache_dir, "certs/server.pem")
        ws = analyze_directory(str(cache_dir), "some_cache")
        assert any("server.pem" in w.relative for w in ws)

    def test_walk_stops_at_depth_3(self, cache_dir):
        """Files deeper than 3 levels are not walked."""
        make_file(cache_dir, "a/b/c/d/deep.pem")   # depth 4
        ws = analyze_directory(str(cache_dir), "some_cache")
        deep_matches = [w for w in ws if "deep.pem" in w.relative]
        assert not deep_matches


# ── Deduplication & ordering ──────────────────────────────────────────────────

class TestDedupAndOrdering:
    def test_no_duplicate_warnings(self, cache_dir):
        make_file(cache_dir, "gradle.properties")
        ws = analyze_directory(str(cache_dir), "gradle_cache")
        paths = [w.file_path for w in ws]
        assert len(paths) == len(set(paths))

    def test_critical_before_warning(self, cache_dir):
        make_file(cache_dir, "gradle.properties")       # critical
        make_file(cache_dir, "init.d/my.gradle")        # warning
        ws = analyze_directory(str(cache_dir), "gradle_cache")
        if len(ws) >= 2:
            assert ws[0].severity in ("critical",)

    def test_multiple_critical_all_returned(self, cache_dir):
        make_file(cache_dir, "settings.xml")
        make_file(cache_dir, "settings-security.xml")
        ws = analyze_directory(str(cache_dir), "maven_cache")
        assert len(ws) >= 2


# ── ContentWarning properties ─────────────────────────────────────────────────

class TestContentWarningProperties:
    def test_icon_critical(self):
        w = ContentWarning("/a/b", "b", "label", "critical")
        assert w.icon == "🔴"

    def test_icon_warning(self):
        w = ContentWarning("/a/b", "b", "label", "warning")
        assert w.icon == "⚠"

    def test_icon_info(self):
        w = ContentWarning("/a/b", "b", "label", "info")
        assert w.icon == "ℹ"

    def test_severity_color_critical(self):
        w = ContentWarning("/a/b", "b", "label", "critical")
        assert w.severity_color == "#f87171"

    def test_severity_color_warning(self):
        w = ContentWarning("/a/b", "b", "label", "warning")
        assert w.severity_color == "#fbbf24"


# ── Helper functions ──────────────────────────────────────────────────────────

class TestHelpers:
    def test_has_critical_warnings_true(self, cache_dir):
        make_file(cache_dir, "gradle.properties")
        ws = analyze_directory(str(cache_dir), "gradle_cache")
        assert has_critical_warnings(ws)

    def test_has_critical_warnings_false(self, cache_dir):
        make_file(cache_dir, "_logs/install.log")
        ws = analyze_directory(str(cache_dir), "npm_cache")
        # npm logs are info — not critical
        assert not has_critical_warnings(ws)

    def test_warnings_by_severity_grouping(self, cache_dir):
        make_file(cache_dir, "gradle.properties")   # critical
        make_file(cache_dir, "init.d/my.gradle")    # warning
        ws = analyze_directory(str(cache_dir), "gradle_cache")
        grouped = warnings_by_severity(ws)
        assert "critical" in grouped
        assert "warning"  in grouped
        assert "info"     in grouped

    def test_empty_warnings_has_critical_false(self):
        assert not has_critical_warnings([])

    def test_warnings_by_severity_empty(self):
        grouped = warnings_by_severity([])
        assert grouped["critical"] == []
        assert grouped["warning"]  == []
        assert grouped["info"]     == []


# ── Real-world scenario: Gradle cache with mixed content ─────────────────────

class TestGradleScenario:
    """Reproduce the exact failure case that motivated this feature."""

    def test_gradle_cache_typical_structure(self, cache_dir):
        # Typical ~/.gradle directory structure
        make_file(cache_dir, "gradle.properties",
                  "org.gradle.jvmargs=-Xmx2048m\nandroid.useAndroidX=true")
        make_file(cache_dir, "caches/modules-2/files-2.1/com.google/guava/guava.jar")
        make_file(cache_dir, "caches/modules-2/metadata.bin")
        make_file(cache_dir, "wrapper/dists/gradle-8.0-bin.zip")
        make_file(cache_dir, "daemon/7.5/daemon.log")

        ws = analyze_directory(str(cache_dir), "gradle_cache")

        # gradle.properties MUST be flagged
        props = [w for w in ws if "gradle.properties" in w.relative]
        assert props, "gradle.properties not detected"
        assert props[0].severity == "critical"

        # JAR/zip/bin files must NOT be flagged
        bad = [w for w in ws if any(
            w.relative.endswith(ext) for ext in (".jar", ".zip", ".bin", ".log")
        )]
        assert not bad, f"Artifact files incorrectly flagged: {[w.relative for w in bad]}"

    def test_analysis_returns_content_warning_objects(self, cache_dir):
        make_file(cache_dir, "gradle.properties")
        ws = analyze_directory(str(cache_dir), "gradle_cache")
        assert all(isinstance(w, ContentWarning) for w in ws)
        for w in ws:
            assert w.file_path
            assert w.relative
            assert w.label
            assert w.severity in ("critical", "warning", "info")
