from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QFrame
)
from PySide6.QtCore import Qt
from app.ui.palettes import NEUTRAL, SEMANTIC


class ScanOverlay(QWidget):
    """Semi-transparent overlay shown during background scan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: rgba(10, 11, 14, 0.88);")
        self._init_ui()
        self.hide()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setStyleSheet(
            "background: #16181c; border: 1px solid #2a2d35; border-radius: 12px;"
        )
        card.setFixedWidth(360)

        cv = QVBoxLayout(card)
        cv.setContentsMargins(28, 26, 28, 26)
        cv.setSpacing(12)

        title = QLabel("Scanning your system…")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cv.addWidget(title)

        self._status_lbl = QLabel("Initializing scanners")
        self._status_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cv.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        cv.addWidget(self._progress)

        self._step_lbl = QLabel("0 / 0 scanners")
        self._step_lbl.setStyleSheet("color: #374151; font-size: 11px;")
        self._step_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cv.addWidget(self._step_lbl)

        outer.addWidget(card)

    def update_progress(self, scanner_name: str, current: int, total: int):
        self._status_lbl.setText(f"Running: {scanner_name}")
        pct = int(current / total * 100) if total else 0
        self._progress.setValue(pct)
        self._step_lbl.setText(f"{current} / {total} scanners complete")

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
