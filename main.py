#!/usr/bin/env python3
"""
DevCache Guardian — Developer Storage Intelligence Platform
Entry point: configures logging, sets app identity, launches the Qt window.

v8 fixes
--------
* Removed AA_UseHighDpiPixmaps (deprecated in PySide6 6.0; high-DPI is automatic)
* App icon loaded from resources/icon.ico (Windows) or resources/icon.png (other)
* QApplication metadata set for proper Windows taskbar identity
"""
import sys
import os

# Project root on sys.path so all app.* imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from pathlib import Path

# ── Logging (before any other import) ────────────────────────────────────────
_log_dir = Path.home() / ".devcache_guardian" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(
    sys.stderr,
    level="WARNING",
    format="<level>{level}</level> | {message}",
)
logger.add(
    str(_log_dir / "guardian_{time:YYYY-MM-DD}.log"),
    rotation="7 days",
    retention="30 days",
    level="DEBUG",
    format="{time:HH:mm:ss} | {level:<8} | {name}:{line} — {message}",
)


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon

    app = QApplication(sys.argv)

    # ── App identity ──────────────────────────────────────────────────────────
    app.setApplicationName("DevCache Guardian")
    app.setApplicationDisplayName("DevCache Guardian")
    app.setApplicationVersion("3.0")
    app.setOrganizationName("DevCache")
    app.setOrganizationDomain("devcache.local")

    # High-DPI is automatic in Qt6/PySide6 — no attribute needed.
    # AA_UseHighDpiPixmaps was removed in Qt 6.0 and raises a DeprecationWarning.

    # ── App icon ──────────────────────────────────────────────────────────────
    _res_dir = Path(__file__).parent / "resources"
    _ico_win = _res_dir / "icon.ico"
    _ico_png = _res_dir / "icon.png"

    icon = None
    if sys.platform == "win32" and _ico_win.exists():
        icon = QIcon(str(_ico_win))
    elif _ico_png.exists():
        icon = QIcon(str(_ico_png))

    if icon and not icon.isNull():
        app.setWindowIcon(icon)
        logger.info(f"App icon loaded from {_ico_win if sys.platform == 'win32' else _ico_png}")
    else:
        logger.warning("App icon not found in resources/ — using default")

    # ── Font ─────────────────────────────────────────────────────────────────
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # ── Launch window ─────────────────────────────────────────────────────────
    from app.ui import MainWindow
    window = MainWindow()
    window.setWindowIcon(icon or QIcon())
    window.show()

    logger.info("DevCache Guardian started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
