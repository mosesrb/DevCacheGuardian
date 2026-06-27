"""
SettingsWidget (v7)

Added
-----
* Scheduled Policies tab — configure per-cache cleanup schedules
* Timeline link hint at bottom
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QListWidget, QListWidgetItem,
    QFileDialog, QScrollArea, QTabWidget,
)
from PySide6.QtCore import Qt

from app.database import (
    get_ignored_paths, add_ignored_path, remove_ignored_path,
    get_preference, set_preference,
)
from app.ui.scheduled_policies_widget import ScheduledPoliciesWidget


def _is_checked(state) -> bool:
    try:
        return state.value == 2
    except AttributeError:
        return int(state) == 2


class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._policies_widget = None
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabBar::tab { background:#16181c; color:#6b7280; border:none;"
            "padding:8px 18px; font-size:12px; border-bottom:2px solid transparent; }"
            "QTabBar::tab:selected { color:#e2e8f0; border-bottom:2px solid #3b82f6; }"
            "QTabBar::tab:hover { color:#c9cdd6; }"
            "QTabWidget::pane { border:none; }"
        )
        tabs.addTab(self._build_general_tab(),  "General")
        tabs.addTab(self._build_policies_tab(), "Scheduled Policies")
        tabs.addTab(self._build_paths_tab(),    "Protected Paths")
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
            k_lbl.setStyleSheet(
                "font-family:'Cascadia Code','Consolas',monospace; font-size:12px;"
                "color:#93c5fd; background:#0d1117; border:1px solid #1e2025;"
                "border-radius:4px; padding:2px 8px;"
            )
            k_lbl.setFixedWidth(165)
            d_lbl = QLabel(desc); d_lbl.setStyleSheet("color:#6b7280; font-size:12px;")
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
        about.setStyleSheet("color:#4b5563; font-size:12px; line-height:1.8;")
        layout.addWidget(about)
        layout.addStretch()
        scroll.setWidget(content)
        return scroll

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
        info.setStyleSheet("color:#6b7280; font-size:12px;")
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
        note.setStyleSheet("color:#4b5563; font-size:12px;")
        note.setWordWrap(True)
        lyt.addWidget(note)

        self._paths_list = QListWidget()
        self._paths_list.setStyleSheet(
            "background:#0d0e10; border:1px solid #1e2025; border-radius:6px;"
            "color:#9ca3af; font-family:'Consolas',monospace; font-size:12px; padding:4px;"
        )
        self._reload_paths()
        lyt.addWidget(self._paths_list, stretch=1)

        btns = QHBoxLayout()
        add_btn = QPushButton("+ Add path"); add_btn.setFixedWidth(110)
        add_btn.clicked.connect(self._add_path)
        rm_btn  = QPushButton("Remove selected"); rm_btn.setFixedWidth(130)
        rm_btn.clicked.connect(self._remove_path)
        btns.addWidget(add_btn); btns.addWidget(rm_btn); btns.addStretch()
        lyt.addLayout(btns)
        return w

    # ── public ────────────────────────────────────────────────────────────────

    def update_scan_items(self, items):
        """Called by main window after each scan to populate policies table."""
        if self._policies_widget:
            self._policies_widget.update_items(items)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size:13px; font-weight:600; color:#9ca3af;")
        return lbl

    def _sep(self):
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine); return f

    def _reload_paths(self):
        self._paths_list.clear()
        for path in get_ignored_paths():
            self._paths_list.addItem(QListWidgetItem(f"🔒  {path}"))

    def _add_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select path to protect")
        if path:
            add_ignored_path(path, reason="User protected")
            self._reload_paths()

    def _remove_path(self):
        selected = self._paths_list.selectedItems()
        if not selected: return
        remove_ignored_path(selected[0].text().replace("🔒  ", "").strip())
        self._reload_paths()
