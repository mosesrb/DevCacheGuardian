"""
theme.py

Runtime theme state for DevCache Guardian.

* Loads the bundled IBM Plex Sans / JetBrains Mono fonts once at startup.
* Holds the currently active palette and persists the choice via the
  existing preferences table (key: "ui_palette").
* Emits a Qt signal when the palette changes so widgets that paint
  manually (QPainter-based widgets, or anything with inline setStyleSheet
  calls that reference colors directly) can refresh themselves without
  a restart.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFontDatabase
from loguru import logger

from app.ui.palettes import get_palette, DEFAULT_PALETTE, PALETTE_ORDER, ACCENTS

_FONT_FILES = [
    "IBMPlexSans-Regular.ttf",
    "IBMPlexSans-Medium.ttf",
    "IBMPlexSans-SemiBold.ttf",
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Medium.ttf",
    "JetBrainsMono-SemiBold.ttf",
]

_fonts_loaded = False


def load_app_fonts() -> None:
    """Register the bundled fonts with Qt. Safe to call once, after a
    QApplication instance exists. Falls back silently (the QSS font-family
    fallback chain takes over) if a font file is missing or fails to load."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    fonts_dir = Path(__file__).resolve().parent.parent.parent / "resources" / "fonts"
    for filename in _FONT_FILES:
        path = fonts_dir / filename
        if not path.exists():
            logger.warning(f"Bundled font missing, falling back to system font: {filename}")
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            logger.warning(f"Failed to register bundled font: {filename}")
    _fonts_loaded = True


class ThemeManager(QObject):
    """Singleton-style holder for the active palette and mode. Import `theme_manager`
    from this module rather than constructing your own instance."""

    palette_changed = Signal(str)  # emits the new palette key

    def __init__(self):
        super().__init__()
        self._key = DEFAULT_PALETTE
        self._mode = "dark"
        self._loaded = False

    def load(self) -> None:
        """Read the persisted palette choice. Call once, after init_db()."""
        if self._loaded:
            return
        try:
            from app.database import get_preference
            key = get_preference("ui_palette", DEFAULT_PALETTE)
            mode = get_preference("ui_mode", "dark")
        except Exception:
            key = DEFAULT_PALETTE
            mode = "dark"
        self._key = key if key in ACCENTS else DEFAULT_PALETTE
        self._mode = mode if mode in ("dark", "light") else "dark"
        self._loaded = True

    def current_key(self) -> str:
        return self._key
        
    def current_mode(self) -> str:
        return self._mode

    def current_palette(self) -> dict:
        return get_palette(self._key, self._mode)

    def set_palette(self, key: str) -> None:
        if key not in ACCENTS or key == self._key:
            return
        self._key = key
        try:
            from app.database import set_preference
            set_preference("ui_palette", key)
        except Exception as e:
            logger.warning(f"Could not persist ui_palette preference: {e}")
        self.palette_changed.emit(key)
        
    def set_mode(self, mode: str) -> None:
        if mode not in ("dark", "light") or mode == self._mode:
            return
        self._mode = mode
        try:
            from app.database import set_preference
            set_preference("ui_mode", mode)
        except Exception as e:
            logger.warning(f"Could not persist ui_mode preference: {e}")
        self.palette_changed.emit(self._key)

    def options(self):
        """Return [(key, label), ...] in display order."""
        return [(k, ACCENTS[k]["label"]) for k in PALETTE_ORDER]


theme_manager = ThemeManager()
