"""
test_scanners.py

Unit tests for scanner path fallback logic when CLI commands fail.
Run with:  pytest tests/test_scanners.py -v
"""
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scanners.npm_scanner import NpmScanner
from app.scanners.pip_scanner import PipScanner
from app.scanners.docker_scanner import DockerScanner
from app.scanners.base_scanner import expand_path


# --- NpmScanner Tests ---

@patch("subprocess.run")
def test_npm_scanner_success(mock_run):
    """Test successful CLI output parsing for npm, pnpm, yarn."""
    mock_run.return_value = MagicMock(returncode=0, stdout="/custom/npm/cache\n")
    scanner = NpmScanner()
    
    assert scanner._get_npm_cache() == "/custom/npm/cache"
    assert scanner._get_pnpm_store() == "/custom/npm/cache"
    assert scanner._get_yarn_cache() == "/custom/npm/cache"


@patch("subprocess.run")
@patch("platform.system")
@patch("pathlib.Path.home")
@patch("app.scanners.npm_scanner.expand_path")
def test_npm_scanner_windows_fallback(mock_expand, mock_home, mock_system, mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="npm", timeout=10)
    mock_system.return_value = "Windows"
    mock_home.return_value = Path("C:/Users/Test")
    mock_expand.side_effect = lambda x: x.replace("%APPDATA%", "C:/Users/Test/AppData/Roaming").replace("%LOCALAPPDATA%", "C:/Users/Test/AppData/Local")
    
    scanner = NpmScanner()
    assert scanner._get_npm_cache() == "C:/Users/Test/AppData/Roaming/npm-cache"
    assert scanner._get_pnpm_store() == "C:/Users/Test/AppData/Local/pnpm/store"
    assert scanner._get_yarn_cache() == "C:/Users/Test/AppData/Local/Yarn/Cache"


@patch("subprocess.run")
@patch("platform.system")
@patch("pathlib.Path.home")
def test_npm_scanner_mac_fallback(mock_home, mock_system, mock_run):
    mock_run.side_effect = Exception("npm not found")
    mock_system.return_value = "Darwin"
    mock_home.return_value = Path("/Users/test")
    
    scanner = NpmScanner()
    assert scanner._get_npm_cache() == str(Path("/Users/test/Library/Caches/npm"))
    assert scanner._get_pnpm_store() == str(Path("/Users/test/Library/pnpm/store"))
    assert scanner._get_yarn_cache() == str(Path("/Users/test/Library/Caches/yarn"))


@patch("subprocess.run")
@patch("platform.system")
@patch("pathlib.Path.home")
def test_npm_scanner_linux_fallback(mock_home, mock_system, mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    mock_system.return_value = "Linux"
    mock_home.return_value = Path("/home/test")
    
    scanner = NpmScanner()
    assert scanner._get_npm_cache() == str(Path("/home/test/.npm"))
    assert scanner._get_pnpm_store() == str(Path("/home/test/.local/share/pnpm/store"))
    assert scanner._get_yarn_cache() == str(Path("/home/test/.cache/yarn"))


# --- PipScanner Tests ---

@patch("subprocess.run")
def test_pip_scanner_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="/custom/pip/cache\n")
    scanner = PipScanner()
    assert scanner._get_pip_cache_dir() == "/custom/pip/cache"


@patch("subprocess.run")
@patch("platform.system")
@patch("pathlib.Path.home")
@patch("app.scanners.pip_scanner.expand_path")
def test_pip_scanner_windows_fallback(mock_expand, mock_home, mock_system, mock_run):
    mock_run.side_effect = Exception("No pip")
    mock_system.return_value = "Windows"
    mock_home.return_value = Path("C:/Users/Test")
    mock_expand.side_effect = lambda x: x.replace("%LOCALAPPDATA%", "C:/Users/Test/AppData/Local")
    
    scanner = PipScanner()
    assert scanner._get_pip_cache_dir() == "C:/Users/Test/AppData/Local/pip/cache"


@patch("subprocess.run")
@patch("platform.system")
@patch("pathlib.Path.home")
def test_pip_scanner_mac_fallback(mock_home, mock_system, mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    mock_system.return_value = "Darwin"
    mock_home.return_value = Path("/Users/test")
    
    scanner = PipScanner()
    assert scanner._get_pip_cache_dir() == str(Path("/Users/test/Library/Caches/pip"))


@patch("subprocess.run")
@patch("platform.system")
@patch("pathlib.Path.home")
@patch("app.scanners.pip_scanner.expand_path")
def test_pip_scanner_linux_fallback(mock_expand, mock_home, mock_system, mock_run):
    mock_run.side_effect = Exception("Failed")
    mock_system.return_value = "Linux"
    mock_home.return_value = Path("/home/test")
    
    # Test fallback when XDG_CACHE_HOME is not set
    mock_expand.side_effect = lambda x: x
    scanner = PipScanner()
    assert scanner._get_pip_cache_dir() == str(Path("/home/test/.cache/pip"))


# --- DockerScanner Tests ---

@patch("subprocess.run")
def test_docker_parse_sizes(mock_run):
    """Test size parsing logic."""
    scanner = DockerScanner()
    assert scanner._parse_size("1GB") == 1024**3
    assert scanner._parse_size("500MB") == 500 * 1024**2
    assert scanner._parse_size("2kB") == 2 * 1024
    assert scanner._parse_size("0B") == 0
    assert scanner._parse_size("invalid") == 0
