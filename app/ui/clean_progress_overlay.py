"""
CleanProgressOverlay — lightweight overlay shown while the CleanWorker thread
is running so the main window stays responsive and visually communicates progress.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QFrame
from PySide6.QtCore import Qt


class CleanProgressOverlay(QWidget):

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

        self._title = QLabel("Cleaning caches…")
        self._title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cv.addWidget(self._title)

        self._status = QLabel("Initialising")
        self._status.setStyleSheet("color: #6b7280; font-size: 12px;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cv.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(6)
        cv.addWidget(self._bar)

        self._step = QLabel("")
        self._step.setStyleSheet("color: #374151; font-size: 11px;")
        self._step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cv.addWidget(self._step)

        outer.addWidget(card)

    def start(self, title: str = "Cleaning caches…"):
        self._title.setText(title)
        self._status.setText("Starting…")
        self._bar.setValue(0)
        self._step.setText("")
        self.show()
        self.raise_()

    def update_progress(self, cache_name: str, current: int, total: int):
        self._status.setText(f"Cleaning: {cache_name}")
        pct = int(current / total * 100) if total else 0
        self._bar.setValue(pct)
        self._step.setText(f"{current} / {total}")

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
