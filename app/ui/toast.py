from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt, QTimer

from app.ui.theme import theme_manager
from app.ui.palettes import SEMANTIC, FONT_SANS


class Toast(QWidget):
    """Slide-in/out toast notification anchored to bottom-right of parent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)

        self._label = QLabel()
        self._label.setStyleSheet(f"color: #fff; font-size: 13px; font-family: {FONT_SANS};")
        layout.addWidget(self._label)

        self.setStyleSheet(f"background: {SEMANTIC['neutral_solid']}; border-radius: 8px;")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide_toast)

        self.hide()

    def show_message(self, message: str, duration_ms: int = 3000, color: str = None):
        color = color or theme_manager.current_palette()["accent"]
        self._label.setText(message)
        self.setStyleSheet(f"background: {color}; border-radius: 8px;")
        self.adjustSize()
        self.setFixedWidth(max(260, self.width()))
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(duration_ms)

    def show_success(self, message: str):
        self.show_message(message, color=SEMANTIC["success_solid"])

    def show_error(self, message: str):
        self.show_message(message, duration_ms=5000, color=SEMANTIC["danger_solid"])

    def _reposition(self):
        if self.parent():
            parent_rect = self.parent().rect()
            x = parent_rect.width() - self.width() - 20
            y = parent_rect.height() - self.height() - 20
            self.move(x, y)

    def _hide_toast(self):
        self.hide()

    def resizeEvent(self, event):
        self._reposition()
        super().resizeEvent(event)
