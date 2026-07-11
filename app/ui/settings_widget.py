"""
SettingsWidget (v9)

v9
--
* Appearance tab — accent palette picker (live, no restart), typography preview
* Removed inline hardcoded QTabBar / label styling in favor of the shared
  app stylesheet (so this screen now follows theme switches automatically)
* Protected-paths list uses a real lock icon instead of an emoji glyph
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QListWidget, QListWidgetItem,
    QFileDialog, QScrollArea, QTabWidget, QRadioButton
)
from PySide6.QtCore import Qt
import qtawesome as qta

from app.database import (
    get_ignored_paths, add_ignored_path, remove_ignored_path,
    get_preference, set_preference,
)
from app.ui.scheduled_policies_widget import ScheduledPoliciesWidget
from app.ui.theme import theme_manager
from app.ui.palettes import ACCENTS, PALETTE_ORDER, NEUTRAL, FONT_SANS, FONT_MONO


def _is_checked(state) -> bool:
    try:
        return state.value == 2
    except AttributeError:
        return int(state) == 2


class PaletteSwatch(QPushButton):
    """A single circular accent-color option in the Appearance picker."""

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        self._color = ACCENTS[key]["accent"]
        self.setCheckable(True)
        self.setFixedSize(34, 34)
        self.setToolTip(ACCENTS[key]["label"])
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_selected(key == theme_manager.current_key())

    def set_selected(self, selected: bool):
        self.setChecked(selected)
        ring = NEUTRAL["text_primary"] if selected else "transparent"
        self.setStyleSheet(
            f"QPushButton {{ background: {self._color}; border-radius: 17px; "
            f"border: 2px solid {ring}; }}"
        )


class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._policies_widget = None
        self._swatches: dict = {}
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(),    "General")
        tabs.addTab(self._build_appearance_tab(), "Appearance")
        tabs.addTab(self._build_policies_tab(),   "Scheduled Policies")
        tabs.addTab(self._build_paths_tab(),      "Protected Paths")
        outer.addWidget(tabs)

    # ── General tab ──────────────────────────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout  = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(22)

        layout.addWidget(self._section("Scan Behaviour"))
        self._cb_startup = QCheckBox("Scan automatically on startup")
        self._cb_startup.setChecked(get_preference("scan_on_startup","true") == "true")
        self._cb_startup.stateChanged.connect(
            lambda s: set_preference("scan_on_startup","true" if _is_checked(s) else "false"))
        layout.addWidget(self._cb_startup)

        self._cb_warning = QCheckBox("Show warning when safe caches exceed 5 GB")
        self._cb_warning.setChecked(get_preference("size_warning_threshold_gb","5") != "0")
        self._cb_warning.stateChanged.connect(
            lambda s: set_preference("size_warning_threshold_gb","5" if _is_checked(s) else "0"))
        layout.addWidget(self._cb_warning)

        layout.addWidget(self._sep())

        layout.addWidget(self._section("Keyboard Shortcuts"))
        for keys, desc in [
            ("F5",               "Re-scan all cache locations"),
            ("Ctrl + D",         "Dry-run all safe caches"),
            ("Ctrl + Shift + C", "Clean all safe caches"),
        ]:
            row = QHBoxLayout()
            k_lbl = QLabel(keys)
            k_lbl.setObjectName("kbdLabel")
            k_lbl.setFixedWidth(165)
            d_lbl = QLabel(desc)
            d_lbl.setObjectName("mutedText")
            row.addWidget(k_lbl); row.addWidget(d_lbl); row.addStretch()
            layout.addLayout(row)

        layout.addWidget(self._sep())
        layout.addWidget(self._section("About"))
        about = QLabel(
            "DevCache Guardian  v3.0\n"
            "Python 3.12 · PySide6 6.6+\n"
            "SQLite · loguru\n\n"
            "A personal tool for developer storage intelligence.\n"
            "Always confirms before deleting. Never touches project files.\n"
            "Data stored in ~/.devcache_guardian/"
        )
        about.setObjectName("mutedText")
        about.setStyleSheet("line-height:1.8;")
        layout.addWidget(about)
        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ── Appearance tab ───────────────────────────────────────────────────────

    def _build_appearance_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout  = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(22)

        layout.addWidget(self._section("Interface Mode"))
        mode_row = QHBoxLayout()
        self._mode_dark_btn = QRadioButton("Dark Mode")
        self._mode_light_btn = QRadioButton("Light Mode")
        
        if theme_manager.current_mode() == "dark":
            self._mode_dark_btn.setChecked(True)
        else:
            self._mode_light_btn.setChecked(True)
            
        self._mode_dark_btn.clicked.connect(lambda: theme_manager.set_mode("dark"))
        self._mode_light_btn.clicked.connect(lambda: theme_manager.set_mode("light"))
        
        mode_row.addWidget(self._mode_dark_btn)
        mode_row.addWidget(self._mode_light_btn)
        mode_row.addStretch()
        layout.addLayout(mode_row)
        
        layout.addWidget(self._sep())

        layout.addWidget(self._section("Accent Palette"))
        note = QLabel(
            "Layout and typography stay the same — only the accent color changes. "
            "Takes effect immediately, no restart needed."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)

        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(14)
        for key in PALETTE_ORDER:
            col = QVBoxLayout()
            col.setSpacing(6)
            swatch = PaletteSwatch(key)
            swatch.clicked.connect(lambda _, k=key: self._select_palette(k))
            self._swatches[key] = swatch

            swatch_wrap = QHBoxLayout()
            swatch_wrap.addWidget(swatch)
            col.addLayout(swatch_wrap)

            lbl = QLabel(ACCENTS[key]["label"])
            lbl.setObjectName("mutedText")
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(lbl)

            wrap = QWidget(); wrap.setLayout(col)
            swatch_row.addWidget(wrap)
        swatch_row.addStretch()
        layout.addLayout(swatch_row)

        layout.addWidget(self._sep())

        layout.addWidget(self._section("Typography"))
        type_row = QHBoxLayout(); type_row.setSpacing(28)

        sans_col = QVBoxLayout(); sans_col.setSpacing(3)
        sans_label = QLabel("Interface — IBM Plex Sans")
        sans_label.setObjectName("mutedText")
        self._sans_sample = QLabel("Cache explorer")
        self._sans_sample.setStyleSheet(f"font-family:{FONT_SANS}; font-size:13px; color:{NEUTRAL['text_secondary']};")
        sans_col.addWidget(sans_label); sans_col.addWidget(self._sans_sample)

        mono_col = QVBoxLayout(); mono_col.setSpacing(3)
        mono_label = QLabel("Data — JetBrains Mono")
        mono_label.setObjectName("mutedText")
        self._mono_sample = QLabel("~/.cache/pip   1.8 GB")
        self._mono_sample.setStyleSheet(f"font-family:{FONT_MONO}; font-size:13px; color:{NEUTRAL['text_secondary']};")
        mono_col.addWidget(mono_label); mono_col.addWidget(self._mono_sample)

        sans_wrap = QWidget(); sans_wrap.setLayout(sans_col)
        mono_wrap = QWidget(); mono_wrap.setLayout(mono_col)
        type_row.addWidget(sans_wrap)
        type_row.addWidget(mono_wrap)
        type_row.addStretch()
        layout.addLayout(type_row)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _select_palette(self, key: str):
        theme_manager.set_palette(key)
        for k, sw in self._swatches.items():
            sw.set_selected(k == key)

    # ── Scheduled Policies tab ────────────────────────────────────────────────

    def _build_policies_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(24, 20, 24, 24)
        lyt.setSpacing(12)

        info = QLabel(
            "Assign a weekly or monthly cleanup schedule to individual caches. "
            "DevCache Guardian will <b>propose</b> cleanups when they are due — "
            "you always confirm before anything is deleted."
        )
        info.setObjectName("mutedText")
        info.setWordWrap(True)
        lyt.addWidget(info)

        self._policies_widget = ScheduledPoliciesWidget()
        lyt.addWidget(self._policies_widget, stretch=1)
        return w

    # ── Protected Paths tab ───────────────────────────────────────────────────

    def _build_paths_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(24, 20, 24, 24)
        lyt.setSpacing(12)

        note = QLabel(
            "Paths listed here are never touched by any cleanup operation, "
            "even if identified as a cache location."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        lyt.addWidget(note)

        self._paths_list = QListWidget()
        self._reload_paths()
        lyt.addWidget(self._paths_list, stretch=1)

        btns = QHBoxLayout()
        self._add_btn = QPushButton("Add path")
        self._add_btn.setIcon(qta.icon("fa5s.plus", color=NEUTRAL["text_secondary"]))
        self._add_btn.setFixedWidth(110)
        self._add_btn.clicked.connect(self._add_path)
        self._rm_btn  = QPushButton("Remove selected")
        self._rm_btn.setIcon(qta.icon("fa5s.trash-alt", color=NEUTRAL["text_secondary"]))
        self._rm_btn.setFixedWidth(150)
        self._rm_btn.clicked.connect(self._remove_path)
        btns.addWidget(self._add_btn); btns.addWidget(self._rm_btn); btns.addStretch()
        lyt.addLayout(btns)
        return w

    # ── public ────────────────────────────────────────────────────────────────

    def update_scan_items(self, items):
        """Called by main window after each scan to populate policies table."""
        if self._policies_widget:
            self._policies_widget.update_items(items)

    def apply_theme(self):
        """Called by MainWindow after a live palette switch."""
        palette = theme_manager.current_palette()
        for k, sw in self._swatches.items():
            sw.set_selected(k == theme_manager.current_key())
            
        if hasattr(self, '_sans_sample'):
            self._sans_sample.setStyleSheet(f"font-family:{FONT_SANS}; font-size:13px; color:{palette['text_secondary']};")
            self._mono_sample.setStyleSheet(f"font-family:{FONT_MONO}; font-size:13px; color:{palette['text_secondary']};")
        if hasattr(self, '_add_btn'):
            self._add_btn.setIcon(qta.icon("fa5s.plus", color=palette["text_secondary"]))
            self._rm_btn.setIcon(qta.icon("fa5s.trash-alt", color=palette["text_secondary"]))
        self._reload_paths()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _sep(self):
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine); return f

    def _reload_paths(self):
        self._paths_list.clear()
        lock_icon = qta.icon("fa5s.lock", color=NEUTRAL["text_faint"])
        for path in get_ignored_paths():
            item = QListWidgetItem(lock_icon, f"  {path}")
            self._paths_list.addItem(item)

    def _add_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select path to protect")
        if path:
            add_ignored_path(path, reason="User protected")
            self._reload_paths()

    def _remove_path(self):
        selected = self._paths_list.selectedItems()
        if not selected: return
        remove_ignored_path(selected[0].text().strip())
        self._reload_paths()
