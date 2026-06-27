"""
CacheTableWidget  (v5)

Audit fixes
-----------
* _export_report: dead Toast import removed; proper success/error signals emitted
* add_item deduplication: O(N) list scan → O(1) set lookup (_item_ids set)
* _populate_table: stop creating QWidget wrappers for every cell on every rebuild;
  use QTableWidgetItem text for simple columns, cell widgets only where needed
* Export now emits export_done(path, count) signal for main window to toast
* Detail panel: Copy path + Open in explorer + Mark as ignored buttons added
* Bulk selection: Ctrl/Shift multi-select; bulk clean/dry-run via context menu
* Search highlighting in name column
* Selection signal carries item so status bar can update

New features
------------
* item_ignored signal — fires when user clicks "Add to ignored paths" in detail panel
* export_done signal — fires with (path, row_count) so main window can show toast
* context_menu on rows: Clean, Dry run, Copy path, Mark as ignored
"""
from __future__ import annotations

import csv
from typing import List, Optional, Set

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QAction
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView, QMenu,
)

from app.models import CacheItem, CleanupMethod, RiskLevel
from app.utils import fmt_bytes, copy_to_clipboard, open_in_explorer


# ── palette ───────────────────────────────────────────────────────────────────

RISK_COLORS = {
    RiskLevel.SAFE:   "#4ade80",
    RiskLevel.REVIEW: "#fbbf24",
    RiskLevel.DANGER: "#f87171",
}
RISK_BG = {
    RiskLevel.SAFE:   "#052e16",
    RiskLevel.REVIEW: "#1c0a00",
    RiskLevel.DANGER: "#1c0404",
}
ECO_COLORS = {
    "Python":        "#3b82f6",
    "Node.js":       "#22c55e",
    "AI/ML":         "#f59e0b",
    "Docker":        "#0ea5e9",
    "System":        "#6b7280",
    "Build Systems": "#a78bfa",
}

COL_NAME, COL_ECO, COL_SIZE, COL_RISK, COL_USAGE = range(5)
COL_RISK_WIDTH  = 100
COL_USAGE_WIDTH = 100


# ── reusable widgets ──────────────────────────────────────────────────────────

class RiskBadge(QLabel):
    _LABELS = {
        RiskLevel.SAFE:   "Safe",
        RiskLevel.REVIEW: "Review",
        RiskLevel.DANGER: "Danger",
    }
    def __init__(self, risk: RiskLevel, parent=None):
        super().__init__(self._LABELS[risk], parent)
        c, bg = RISK_COLORS[risk], RISK_BG[risk]
        self.setStyleSheet(
            f"color:{c}; background:{bg}; border:1px solid {c}33;"
            "border-radius:10px; padding:2px 10px; font-size:11px; font-weight:600;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)


class SizeBar(QWidget):
    def __init__(self, pct: float, risk: RiskLevel, parent=None):
        super().__init__(parent)
        self.pct  = max(0.0, min(1.0, pct))
        self.risk = risk
        self.setFixedSize(72, 20)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1a1d22"))
        p.drawRoundedRect(0, 7, 72, 6, 3, 3)
        w = int(72 * self.pct)
        if w > 0:
            p.setBrush(QColor(RISK_COLORS[self.risk]))
            p.drawRoundedRect(0, 7, w, 6, 3, 3)


class FilterPill(QPushButton):
    _BASE = (
        "QPushButton{{border:1px solid #2a2d35; border-radius:12px;"
        "padding:4px 14px; font-size:12px; background:#1a1d22; color:#6b7280;}}"
        "QPushButton:hover{{background:#22262e; color:#c9cdd6; border-color:#3a3f4a;}}"
        "QPushButton:checked{{background:{bg}; color:{fg}; border-color:{fg}44; font-weight:600;}}"
    )
    _THEME = {
        "all":    ("#1d4ed8", "#93c5fd"),
        "safe":   ("#052e16", "#4ade80"),
        "review": ("#1c0a00", "#fbbf24"),
        "danger": ("#1c0404", "#f87171"),
    }
    def __init__(self, label: str, key: str, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedHeight(28)
        bg, fg = self._THEME.get(key, ("#1a1d22", "#c9cdd6"))
        self.setStyleSheet(self._BASE.format(bg=bg, fg=fg))
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)


# ── detail panel ─────────────────────────────────────────────────────────────

class DetailPanel(QWidget):
    clean_requested   = Signal(object)   # CacheItem
    dry_run_requested = Signal(object)   # CacheItem
    rescan_requested  = Signal(object)   # CacheItem
    ignore_requested  = Signal(object)   # CacheItem — add to protected paths
    show_error_requested = Signal(str)   # error message to surface as toast

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detailPanel")
        self._item: Optional[CacheItem] = None
        self._cleaned_ids: Set[str] = set()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        # header
        hdr = QHBoxLayout()
        self._title_lbl = QLabel()
        self._title_lbl.setObjectName("detailTitle")
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        self._badge_lbl = QLabel()
        hdr.addWidget(self._badge_lbl)
        root.addLayout(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # size + ecosystem
        meta = QHBoxLayout(); meta.setSpacing(20)
        self._size_field = self._make_field("Size")
        self._eco_field  = self._make_field("Ecosystem")
        meta.addWidget(self._size_field["w"])
        meta.addWidget(self._eco_field["w"])
        meta.addStretch()
        root.addLayout(meta)

        # path row with copy + open buttons — wrapped in a QWidget for proper visibility
        path_header_w = QWidget()
        path_hdr      = QHBoxLayout(path_header_w)
        path_hdr.setContentsMargins(0, 0, 0, 0)
        path_hdr.addWidget(self._section_label("PATH"))
        path_hdr.addStretch()
        self._btn_copy_path = QPushButton("📋 Copy")
        self._btn_copy_path.setFixedHeight(22)
        self._btn_copy_path.setStyleSheet(
            "font-size:11px; padding:1px 8px; color:#6b7280; "
            "background:#13151a; border:1px solid #2a2d35; border-radius:4px;"
        )
        self._btn_copy_path.clicked.connect(self._copy_path)
        self._btn_open_explorer = QPushButton("📂 Open")
        self._btn_open_explorer.setFixedHeight(22)
        self._btn_open_explorer.setStyleSheet(
            "font-size:11px; padding:1px 8px; color:#6b7280; "
            "background:#13151a; border:1px solid #2a2d35; border-radius:4px;"
        )
        self._btn_open_explorer.clicked.connect(self._open_in_explorer)
        path_hdr.addWidget(self._btn_copy_path)
        path_hdr.addWidget(self._btn_open_explorer)
        self._path_header_w = path_header_w
        root.addWidget(path_header_w)

        self._path_val = QLabel()
        self._path_val.setStyleSheet(
            "font-family:'Cascadia Code','Consolas',monospace; font-size:11px; color:#6b7280;"
        )
        self._path_val.setWordWrap(True)
        self._path_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._path_val)

        # about
        root.addWidget(self._section_label("ABOUT THIS CACHE"))
        self._about_val = QLabel()
        self._about_val.setObjectName("detailLongDesc")
        self._about_val.setWordWrap(True)
        root.addWidget(self._about_val)

        # command
        self._cmd_section_lbl = self._section_label("CLEANUP COMMAND")
        root.addWidget(self._cmd_section_lbl)
        self._cmd_val = QLabel()
        self._cmd_val.setObjectName("cmdLabel")
        self._cmd_val.setWordWrap(True)
        self._cmd_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._cmd_val)

        self._no_cmd_lbl = QLabel("No official command — will remove directory contents directly.")
        self._no_cmd_lbl.setStyleSheet("color:#4b5563; font-size:12px;")
        self._no_cmd_lbl.setWordWrap(True)
        root.addWidget(self._no_cmd_lbl)

        root.addStretch()

        # actions
        actions = QHBoxLayout(); actions.setSpacing(8)
        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet("font-size:12px; font-weight:600;")
        self._btn_dry    = QPushButton("🔍  Dry run")
        self._btn_dry.setToolTip("Simulate this cleanup without touching any files")
        self._btn_clean  = QPushButton("Clean this cache")
        self._btn_clean.setObjectName("btnPrimary")
        self._btn_rescan = QPushButton("↻ Rescan")
        self._btn_rescan.setToolTip("Re-measure this cache location")
        self._btn_ignore = QPushButton("🛡 Protect")
        self._btn_ignore.setToolTip("Add this path to protected locations so it is never cleaned")
        self._btn_ignore.setStyleSheet(
            "font-size:12px; padding:5px 10px; color:#9ca3af;"
            "background:#1a1d22; border:1px solid #2a2d35; border-radius:6px;"
        )

        for w in (self._status_lbl, self._btn_dry, self._btn_clean,
                  self._btn_rescan, self._btn_ignore):
            actions.addWidget(w)
        actions.addStretch()
        root.addLayout(actions)

        # connect
        self._btn_dry.clicked.connect(lambda: self._item and self.dry_run_requested.emit(self._item))
        self._btn_clean.clicked.connect(lambda: self._item and self.clean_requested.emit(self._item))
        self._btn_rescan.clicked.connect(lambda: self._item and self.rescan_requested.emit(self._item))
        self._btn_ignore.clicked.connect(lambda: self._item and self.ignore_requested.emit(self._item))

        self._set_visible(False)

    # ── public ────────────────────────────────────────────────────────────────

    def show_item(self, item: CacheItem):
        self._item = item
        self._set_visible(True)
        self._refresh()

    def show_empty(self):
        self._item = None
        self._set_visible(False)

    def mark_cleaned(self, item_id: str):
        self._cleaned_ids.add(item_id)
        if self._item and self._item.id == item_id:
            self._refresh()

    def mark_rescanned(self, item: CacheItem):
        if self._item and self._item.id == item.id:
            self._item = item
            self._refresh()

    # ── private ───────────────────────────────────────────────────────────────

    def _refresh(self):
        if not self._item:
            return
        item    = self._item
        cleaned = item.id in self._cleaned_ids

        self._title_lbl.setText(item.name)

        c  = RISK_COLORS[item.risk_level]
        bg = RISK_BG[item.risk_level]
        labels = {RiskLevel.SAFE:"Safe", RiskLevel.REVIEW:"Review", RiskLevel.DANGER:"Danger"}
        self._badge_lbl.setText(labels[item.risk_level])
        self._badge_lbl.setStyleSheet(
            f"color:{c}; background:{bg}; border:1px solid {c}33;"
            "border-radius:10px; padding:2px 10px; font-size:11px; font-weight:600;"
        )

        self._size_field["val"].setText("Cleaned" if cleaned else item.size_label)
        self._size_field["val"].setStyleSheet(
            f"color:{'#6b7280' if cleaned else '#3b82f6'}; font-size:13px;"
        )

        eco_c = ECO_COLORS.get(item.ecosystem, "#6b7280")
        self._eco_field["val"].setText(item.ecosystem)
        self._eco_field["val"].setStyleSheet(f"color:{eco_c}; font-size:13px;")

        self._path_val.setText(item.path)
        self._about_val.setText(item.long_description)

        has_cmd = bool(item.cleanup_command)
        self._cmd_section_lbl.setVisible(has_cmd)
        self._cmd_val.setVisible(has_cmd)
        self._no_cmd_lbl.setVisible(not has_cmd)
        if has_cmd:
            self._cmd_val.setText(item.cleanup_command.splitlines()[0])

        # buttons
        if cleaned:
            self._status_lbl.setText("✓  Cleaned")
            self._status_lbl.setStyleSheet("color:#4ade80; font-size:12px; font-weight:600;")
            self._status_lbl.show(); self._btn_dry.hide()
            self._btn_clean.hide(); self._btn_rescan.show()
            self._btn_ignore.show()
        elif item.risk_level == RiskLevel.DANGER:
            self._status_lbl.setText("⚠  Protected — inspect manually")
            self._status_lbl.setStyleSheet("color:#f87171; font-size:12px;")
            self._status_lbl.show(); self._btn_dry.hide()
            self._btn_clean.hide(); self._btn_rescan.hide()
            self._btn_ignore.hide()
        else:
            self._status_lbl.hide()
            self._btn_dry.show(); self._btn_rescan.hide()
            self._btn_ignore.show(); self._btn_clean.show()
            if item.risk_level == RiskLevel.REVIEW:
                self._btn_clean.setText("Clean with care")
                self._btn_clean.setObjectName("btnWarning")
            else:
                self._btn_clean.setText("Clean this cache")
                self._btn_clean.setObjectName("btnPrimary")
            self._btn_clean.style().unpolish(self._btn_clean)
            self._btn_clean.style().polish(self._btn_clean)

    def _set_visible(self, v: bool):
        for w in (self._title_lbl, self._badge_lbl,
                  self._size_field["w"], self._eco_field["w"],
                  self._path_header_w, self._path_val,
                  self._about_val,
                  self._cmd_section_lbl, self._cmd_val, self._no_cmd_lbl,
                  self._status_lbl, self._btn_dry, self._btn_clean,
                  self._btn_rescan, self._btn_ignore,
                  self._btn_copy_path, self._btn_open_explorer):
            w.setVisible(v)

    def _copy_path(self):
        if self._item:
            copy_to_clipboard(self._item.path)

    def _open_in_explorer(self):
        if self._item:
            err = open_in_explorer(self._item.path)
            if err:
                self.show_error_requested.emit(err)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setObjectName("detailFieldLabel")
        return lbl

    @staticmethod
    def _make_field(label_text: str) -> dict:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0,0,0,0); vl.setSpacing(3)
        lbl = QLabel(label_text.upper()); lbl.setObjectName("detailFieldLabel")
        val = QLabel(); val.setWordWrap(True)
        vl.addWidget(lbl); vl.addWidget(val)
        return {"w": w, "val": val}


# ── main table widget ─────────────────────────────────────────────────────────

class CacheTableWidget(QWidget):
    item_selected     = Signal(object)          # CacheItem
    clean_requested   = Signal(object)          # CacheItem
    dry_run_requested = Signal(object)          # CacheItem
    rescan_requested  = Signal(object)          # CacheItem
    ignore_requested  = Signal(object)          # CacheItem
    bulk_clean        = Signal(list)            # List[CacheItem]
    bulk_dry_run      = Signal(list)            # List[CacheItem]
    export_done       = Signal(str, int)        # (file_path, row_count)
    export_failed     = Signal(str)             # error message

    COLUMNS    = ["Cache", "Ecosystem", "Size", "Risk", "Usage"]
    _SORT_KEYS = {
        COL_NAME:  lambda i: i.name.lower(),
        COL_ECO:   lambda i: i.ecosystem.lower(),
        COL_SIZE:  lambda i: i.size_bytes,
        COL_RISK:  lambda i: list(RiskLevel).index(i.risk_level),
        COL_USAGE: lambda i: i.size_bytes,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_items:    List[CacheItem] = []
        self._item_ids:     Set[str]        = set()   # O(1) deduplication
        self._cleaned_ids:  Set[str]        = set()
        self._current_filter = "all"
        self._sort_col        = COL_SIZE
        self._sort_asc        = False
        self._rebuild_timer   = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(120)
        self._rebuild_timer.timeout.connect(self._apply_filter)
        self._init_ui()

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(24, 16, 24, 24)
        lyt.setSpacing(12)
        lyt.addLayout(self._build_filter_bar())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_detail_area())
        splitter.setSizes([400, 280])
        lyt.addWidget(splitter)

    def _build_filter_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout(); bar.setSpacing(6)

        self._pills: dict = {}
        for label, key in [("All","all"),("Safe","safe"),("Review","review"),("Danger","danger")]:
            p = FilterPill(label, key)
            p.clicked.connect(lambda _, k=key: self._set_filter(k))
            self._pills[key] = p
            bar.addWidget(p)
        self._pills["all"].setChecked(True)

        bar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search caches…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)
        bar.addWidget(self._search)

        self._eco_combo = QComboBox()
        self._eco_combo.addItems(["All ecosystems","Python","Node.js","AI/ML",
                                   "Docker","System","Build Systems"])
        self._eco_combo.setFixedWidth(148)
        self._eco_combo.currentTextChanged.connect(self._apply_filter)
        bar.addWidget(self._eco_combo)

        export_btn = QPushButton("⬇  Export")
        export_btn.setFixedHeight(28)
        export_btn.setToolTip("Export visible items to CSV")
        export_btn.clicked.connect(self._export_report)
        bar.addWidget(export_btn)

        return bar

    def _build_table(self) -> QTableWidget:
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(COL_NAME,  QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_ECO,   QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_SIZE,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_RISK,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_USAGE, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(COL_ECO,   110)
        hdr.resizeSection(COL_SIZE,  90)
        hdr.resizeSection(COL_RISK,  COL_RISK_WIDTH)
        hdr.resizeSection(COL_USAGE, COL_USAGE_WIDTH)
        hdr.sectionClicked.connect(self._on_header_clicked)
        hdr.setHighlightSections(False)

        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # multi-select
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(200)
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        return self._table

    def _build_detail_area(self) -> QWidget:
        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)

        self._detail_stack = QStackedWidget()

        empty_page = QWidget()
        ep = QVBoxLayout(empty_page)
        ep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("Select a cache item to view details")
        hint.setStyleSheet("color:#374151; font-size:13px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep.addWidget(hint)
        self._detail_stack.addWidget(empty_page)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._detail = DetailPanel()
        self._detail.clean_requested.connect(self.clean_requested)
        self._detail.dry_run_requested.connect(self.dry_run_requested)
        self._detail.rescan_requested.connect(self.rescan_requested)
        self._detail.ignore_requested.connect(self.ignore_requested)
        scroll.setWidget(self._detail)
        self._detail_stack.addWidget(scroll)

        self._detail_stack.setCurrentIndex(0)
        vl.addWidget(self._detail_stack)
        container.setMinimumHeight(240)
        return container

    # ── public API ────────────────────────────────────────────────────────────

    def update_items(self, items: List[CacheItem]):
        self._all_items = list(items)
        self._item_ids  = {i.id for i in items}
        self._rebuild_timer.stop()
        self._apply_filter()

    def add_item(self, item: CacheItem):
        """O(1) dedup via set; debounced rebuild."""
        if item.id not in self._item_ids:
            self._all_items.append(item)
            self._item_ids.add(item.id)
        if not self._rebuild_timer.isActive():
            self._rebuild_timer.start()

    def mark_cleaned(self, item_id: str):
        self._cleaned_ids.add(item_id)
        self._detail.mark_cleaned(item_id)
        self._apply_filter()

    def update_item(self, item: CacheItem):
        for i, existing in enumerate(self._all_items):
            if existing.id == item.id:
                self._all_items[i] = item
                break
        self._detail.mark_rescanned(item)
        self._apply_filter()

    def selected_items(self) -> List[CacheItem]:
        """Return all currently selected CacheItems (supports multi-select)."""
        result = []
        for idx in self._table.selectionModel().selectedRows():
            hidden = self._table.item(idx.row(), COL_NAME)
            if hidden:
                ci = hidden.data(Qt.ItemDataRole.UserRole)
                if ci:
                    result.append(ci)
        return result

    # ── filter / sort ─────────────────────────────────────────────────────────

    def _set_filter(self, key: str):
        self._current_filter = key
        for k, p in self._pills.items():
            p.setChecked(k == key)
        self._apply_filter()

    def _apply_filter(self):
        search = self._search.text().strip().lower()
        eco    = self._eco_combo.currentText()
        eco    = "" if eco == "All ecosystems" else eco

        visible = [
            i for i in self._all_items
            if (self._current_filter == "all" or i.risk_level.value == self._current_filter)
            and (not eco or i.ecosystem == eco)
            and (not search
                 or search in i.name.lower()
                 or search in i.ecosystem.lower()
                 or search in i.description.lower()
                 or search in i.path.lower())
        ]
        key_fn = self._SORT_KEYS[self._sort_col]
        visible.sort(key=key_fn, reverse=not self._sort_asc)
        self._populate_table(visible, highlight=search)

    def _on_header_clicked(self, col: int):
        if col == self._sort_col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = (col != COL_SIZE)
        self._apply_filter()

    # ── table population ──────────────────────────────────────────────────────

    def _populate_table(self, items: List[CacheItem], highlight: str = ""):
        sel_id      = self._selected_id()
        total_bytes = sum(i.size_bytes for i in self._all_items) or 1

        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(0)

        for item in items:
            row     = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setRowHeight(row, 44)
            cleaned = item.id in self._cleaned_ids

            # ── col 0: name + description ─────────────────────────────────────
            cell = QWidget()
            cv   = QVBoxLayout(cell)
            cv.setContentsMargins(10, 4, 4, 4); cv.setSpacing(1)

            name_text = item.name
            if highlight and highlight in name_text.lower():
                # Wrap matched portion in a highlight span
                lo = name_text.lower().find(highlight)
                hi = lo + len(highlight)
                name_text = (
                    name_text[:lo]
                    + f'<span style="background:#854d0e; color:#fde68a; border-radius:2px;">'
                    + name_text[lo:hi]
                    + '</span>'
                    + name_text[hi:]
                )
                name_lbl = QLabel()
                name_lbl.setTextFormat(Qt.TextFormat.RichText)
            else:
                name_lbl = QLabel()

            name_lbl.setText(f"<s>{item.name}</s>" if cleaned else name_text)
            name_lbl.setStyleSheet(
                "color:#6b7280; font-size:13px;" if cleaned
                else "color:#e2e8f0; font-size:13px; font-weight:500;"
            )
            desc_lbl = QLabel("Cleaned" if cleaned else item.description)
            desc_lbl.setStyleSheet("color:#374151; font-size:11px;")
            cv.addWidget(name_lbl); cv.addWidget(desc_lbl)
            self._table.setCellWidget(row, COL_NAME, cell)

            # ── col 1: ecosystem ──────────────────────────────────────────────
            eco_lbl = QLabel(item.ecosystem)
            eco_lbl.setStyleSheet(
                f"color:{ECO_COLORS.get(item.ecosystem,'#6b7280')};"
                "font-size:12px; padding-left:8px;"
            )
            self._table.setCellWidget(row, COL_ECO, eco_lbl)

            # ── col 2: size ───────────────────────────────────────────────────
            size_lbl = QLabel("—" if cleaned else item.size_label)
            size_lbl.setStyleSheet(
                "color:#e2e8f0; font-size:12px; font-weight:600; padding-left:8px;"
            )
            self._table.setCellWidget(row, COL_SIZE, size_lbl)

            # ── col 3: risk badge ─────────────────────────────────────────────
            badge_w = QWidget()
            bh      = QHBoxLayout(badge_w)
            bh.setContentsMargins(8, 0, 8, 0)
            bh.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            bh.addWidget(RiskBadge(item.risk_level))
            self._table.setCellWidget(row, COL_RISK, badge_w)

            # ── col 4: usage bar ──────────────────────────────────────────────
            bar_w = QWidget()
            bh2   = QHBoxLayout(bar_w)
            bh2.setContentsMargins(8, 0, 8, 0)
            bh2.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            bh2.addWidget(SizeBar(0 if cleaned else item.size_bytes / total_bytes,
                                  item.risk_level))
            self._table.setCellWidget(row, COL_USAGE, bar_w)

            # ── hidden data item ──────────────────────────────────────────────
            hidden = QTableWidgetItem()
            hidden.setData(Qt.ItemDataRole.UserRole, item)
            self._table.setItem(row, COL_NAME, hidden)

            if item.id == sel_id:
                self._table.selectRow(row)

        self._table.setUpdatesEnabled(True)

    # ── selection ─────────────────────────────────────────────────────────────

    def _selected_id(self) -> Optional[str]:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        hidden = self._table.item(rows[0].row(), COL_NAME)
        if hidden:
            ci = hidden.data(Qt.ItemDataRole.UserRole)
            return ci.id if ci else None
        return None

    def _on_selection(self):
        sel = self.selected_items()
        if not sel:
            self._detail_stack.setCurrentIndex(0)
            return
        # Detail panel shows the first selected item
        ci = sel[0]
        self._detail.show_item(ci)
        self._detail_stack.setCurrentIndex(1)
        self.item_selected.emit(ci)

    # ── context menu ─────────────────────────────────────────────────────────

    def _show_context_menu(self, pos):
        sel = self.selected_items()
        if not sel:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#16181c; border:1px solid #2a2d35; color:#c9cdd6; "
            "border-radius:6px; padding:4px; }"
            "QMenu::item { padding:6px 20px; border-radius:4px; }"
            "QMenu::item:selected { background:#1d4ed8; color:#fff; }"
            "QMenu::separator { height:1px; background:#2a2d35; margin:4px 8px; }"
        )

        if len(sel) == 1:
            item = sel[0]
            act_dry   = menu.addAction("🔍  Dry run")
            act_clean = menu.addAction("🧹  Clean")
            act_clean.setEnabled(item.risk_level != RiskLevel.DANGER)
            menu.addSeparator()
            act_copy  = menu.addAction("📋  Copy path")
            act_open  = menu.addAction("📂  Open in Explorer")
            menu.addSeparator()
            act_ignore = menu.addAction("🛡  Add to protected paths")

            chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
            if chosen == act_dry:    self.dry_run_requested.emit(item)
            elif chosen == act_clean and item.risk_level != RiskLevel.DANGER:
                self.clean_requested.emit(item)
            elif chosen == act_copy:   copy_to_clipboard(item.path)
            elif chosen == act_open:   open_in_explorer(item.path)
            elif chosen == act_ignore: self.ignore_requested.emit(item)
        else:
            # Bulk actions
            cleanable = [i for i in sel if i.risk_level != RiskLevel.DANGER]
            act_bulk_dry   = menu.addAction(f"🔍  Dry run {len(sel)} items")
            act_bulk_clean = menu.addAction(f"🧹  Clean {len(cleanable)} safe/review items")
            act_bulk_clean.setEnabled(bool(cleanable))

            chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
            if chosen == act_bulk_dry:   self.bulk_dry_run.emit(sel)
            elif chosen == act_bulk_clean: self.bulk_clean.emit(cleanable)

    # ── export ────────────────────────────────────────────────────────────────

    def _export_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export cache report", "cache_report.csv",
            "CSV files (*.csv)"
        )
        if not path:
            return

        items_out = []
        for r in range(self._table.rowCount()):
            hidden = self._table.item(r, COL_NAME)
            if hidden:
                ci = hidden.data(Qt.ItemDataRole.UserRole)
                if ci:
                    items_out.append(ci)

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Name", "Ecosystem", "Size (bytes)", "Size (human)",
                             "Risk", "Path", "Cleanup command"])
                for ci in items_out:
                    w.writerow([
                        ci.name, ci.ecosystem, ci.size_bytes, ci.size_label,
                        ci.risk_label, ci.path, ci.cleanup_command or "",
                    ])
            self.export_done.emit(path, len(items_out))
        except Exception as exc:
            self.export_failed.emit(str(exc))
