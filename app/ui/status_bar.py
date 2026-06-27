"""
StatusBar — persistent bottom bar showing scan state, selection info,
and the last action result.  Lives at the bottom of MainWindow below
the stacked content area.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class StatusBar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(28)
        self.setStyleSheet(
            "QWidget#statusBar {"
            "  background: #0d0e10;"
            "  border-top: 1px solid #1e2025;"
            "}"
            "QLabel { font-size: 11px; color: #374151; }"
        )

        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(16, 0, 16, 0)
        lyt.setSpacing(20)

        self._scan_lbl    = self._dot_label("●", "#374151", "No scan yet")
        self._items_lbl   = QLabel("")
        self._sel_lbl     = QLabel("")
        self._action_lbl  = QLabel("")
        self._action_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        lyt.addWidget(self._scan_lbl)
        lyt.addWidget(self._items_lbl)
        lyt.addWidget(self._sel_lbl)
        lyt.addStretch()
        lyt.addWidget(self._action_lbl)

        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(lambda: self._action_lbl.setText(""))

    # ── public ────────────────────────────────────────────────────────────────

    def set_scanning(self, scanner_name: str):
        self._scan_dot("●", "#3b82f6")
        self._scan_lbl.setText(f"● Scanning: {scanner_name}")
        self._scan_lbl.setStyleSheet("font-size:11px; color:#3b82f6;")

    def set_scan_complete(self, item_count: int, total_bytes: int, duration_s: float):
        from app.utils import fmt_bytes
        self._scan_dot("●", "#4ade80")
        dur = f"{duration_s:.1f}s" if duration_s >= 1 else f"{duration_s*1000:.0f}ms"
        self._scan_lbl.setStyleSheet("font-size:11px; color:#4ade80;")
        self._scan_lbl.setText(f"● Ready — {fmt_bytes(total_bytes)} in {dur}")
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

    def set_action(self, message: str, color: str = "#4ade80", timeout_ms: int = 4000):
        self._action_lbl.setStyleSheet(f"font-size:11px; color:{color};")
        self._action_lbl.setText(message)
        if timeout_ms > 0:
            self._clear_timer.start(timeout_ms)

    def clear(self):
        self._action_lbl.setText("")
        self._sel_lbl.setText("")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _scan_dot(self, dot: str, color: str):
        pass  # colour set inline above

    @staticmethod
    def _dot_label(dot: str, color: str, text: str) -> QLabel:
        lbl = QLabel(f"{dot} {text}")
        lbl.setStyleSheet(f"font-size:11px; color:{color};")
        return lbl
