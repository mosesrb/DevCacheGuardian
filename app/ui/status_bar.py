"""
StatusBar — persistent bottom bar showing scan state, selection info,
and the last action result.  Lives at the bottom of MainWindow below
the stacked content area.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from app.ui.theme import theme_manager
from app.ui.palettes import NEUTRAL, SEMANTIC


class StatusBar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(28)
        self._scan_state = "idle"   # idle | scanning | complete
        self._scan_text  = "No scan yet"
        self._apply_bar_style()

        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(16, 0, 16, 0)
        lyt.setSpacing(20)

        self._scan_lbl    = QLabel(f"●  {self._scan_text}")
        self._items_lbl   = QLabel("")
        self._sel_lbl     = QLabel("")
        self._action_lbl  = QLabel("")
        self._action_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        for lbl in (self._items_lbl, self._sel_lbl):
            lbl.setObjectName("mutedText")

        lyt.addWidget(self._scan_lbl)
        lyt.addWidget(self._items_lbl)
        lyt.addWidget(self._sel_lbl)
        lyt.addStretch()
        lyt.addWidget(self._action_lbl)

        self._restyle_scan_label()

        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(lambda: self._action_lbl.setText(""))

    def _apply_bar_style(self):
        self.setStyleSheet(
            f"QWidget#statusBar {{"
            f"  background: {NEUTRAL['bg_sidebar']};"
            f"  border-top: 1px solid {NEUTRAL['border']};"
            f"}}"
            f"QLabel {{ font-size: 11px; color: {NEUTRAL['text_faint']}; }}"
        )

    def _restyle_scan_label(self):
        color = {
            "idle":      NEUTRAL["text_faint"],
            "scanning":  theme_manager.current_palette()["accent"],
            "complete":  SEMANTIC["success"],
        }.get(self._scan_state, NEUTRAL["text_faint"])
        self._scan_lbl.setStyleSheet(f"font-size:11px; color:{color};")
        self._scan_lbl.setText(f"●  {self._scan_text}")

    # ── public ────────────────────────────────────────────────────────────────

    def set_scanning(self, scanner_name: str):
        self._scan_state = "scanning"
        self._scan_text  = f"Scanning: {scanner_name}"
        self._restyle_scan_label()

    def set_scan_complete(self, item_count: int, total_bytes: int, duration_s: float):
        from app.utils import fmt_bytes
        self._scan_state = "complete"
        dur = f"{duration_s:.1f}s" if duration_s >= 1 else f"{duration_s*1000:.0f}ms"
        self._scan_text  = f"Ready — {fmt_bytes(total_bytes)} in {dur}"
        self._restyle_scan_label()
        self._items_lbl.setText(f"{item_count} locations")

    def set_item_count(self, total: int, safe: int, review: int, danger: int):
        parts = []
        if safe:    parts.append(f"{safe} safe")
        if review:  parts.append(f"{review} review")
        if danger:  parts.append(f"{danger} protected")
        self._items_lbl.setText("  ·  ".join(parts))

    def set_selection(self, item_name: str, item_size: str):
        if item_name:
            self._sel_lbl.setText(f"Selected: {item_name}  ({item_size})")
        else:
            self._sel_lbl.setText("")

    def set_action(self, message: str, color: str = None, timeout_ms: int = 4000):
        color = color or SEMANTIC["success"]
        self._action_lbl.setStyleSheet(f"font-size:11px; color:{color};")
        self._action_lbl.setText(message)
        if timeout_ms > 0:
            self._clear_timer.start(timeout_ms)

    def clear(self):
        self._action_lbl.setText("")
        self._sel_lbl.setText("")

    def apply_theme(self):
        """Called by MainWindow after a live palette switch."""
        self._apply_bar_style()
        self._restyle_scan_label()
