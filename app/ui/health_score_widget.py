"""
HealthScoreWidget — displays the system health score as a circular gauge
with a grade letter and breakdown stats underneath.
"""
from __future__ import annotations

import math
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)
from app.utils import fmt_bytes


_GRADE_COLORS = {
    "A": "#4ade80", "B": "#86efac",
    "C": "#fbbf24", "D": "#f97316", "F": "#f87171",
}


class ScoreGauge(QWidget):
    """Circular arc gauge showing 0-100 score."""

    def __init__(self, score: int = 100, grade: str = "A", parent=None):
        super().__init__(parent)
        self.score = score
        self.grade = grade
        self.setFixedSize(110, 110)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def update_score(self, score: int, grade: str):
        self.score = score
        self.grade = grade
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h    = self.width(), self.height()
        cx, cy  = w // 2, h // 2
        r       = min(w, h) // 2 - 10
        color   = _GRADE_COLORS.get(self.grade, "#6b7280")

        # Background track
        pen = QPen(QColor("#1e2025"), 8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(cx - r, cy - r, r * 2, r * 2, 225 * 16, -270 * 16)

        # Score arc
        if self.score > 0:
            pen2 = QPen(QColor(color), 8)
            pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen2)
            span = int(-270 * 16 * self.score / 100)
            p.drawArc(cx - r, cy - r, r * 2, r * 2, 225 * 16, span)

        # Score number
        p.setPen(QColor(color))
        f1 = QFont(); f1.setPointSize(18); f1.setBold(True)
        p.setFont(f1)
        p.drawText(0, 0, w, h - 10,
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   str(self.score))

        # Grade below number
        p.setPen(QColor("#6b7280"))
        f2 = QFont(); f2.setPointSize(10)
        p.setFont(f2)
        p.drawText(0, 20, w, h,
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   f"/ 100")


class HealthScoreWidget(QWidget):
    """Full health score card: gauge + breakdown stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self._build()

    def _build(self):
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(16, 14, 16, 14)
        lyt.setSpacing(20)

        self._gauge = ScoreGauge()
        lyt.addWidget(self._gauge)

        right = QVBoxLayout()
        right.setSpacing(4)

        self._title = QLabel("Health score")
        self._title.setObjectName("metricLabel")
        right.addWidget(self._title)

        self._grade_lbl = QLabel("—")
        self._grade_lbl.setStyleSheet("font-size:20px; font-weight:700; color:#e2e8f0;")
        right.addWidget(self._grade_lbl)

        self._safe_lbl   = QLabel()
        self._review_lbl = QLabel()
        self._total_lbl  = QLabel()
        for lbl in (self._safe_lbl, self._review_lbl, self._total_lbl):
            lbl.setStyleSheet("font-size:11px; color:#4b5563;")
            right.addWidget(lbl)

        right.addStretch()
        lyt.addLayout(right)

    def update_health(self, health: dict):
        score = health.get("score", 0)
        grade = health.get("grade", "?")
        bd    = health.get("breakdown", {})
        color = _GRADE_COLORS.get(grade, "#6b7280")

        self._gauge.update_score(score, grade)
        self._grade_lbl.setText(f"Grade  {grade}")
        self._grade_lbl.setStyleSheet(f"font-size:20px; font-weight:700; color:{color};")
        self._safe_lbl.setText(f"Safe:    {bd.get('safe_reclaimable','—')}")
        self._review_lbl.setText(f"Review: {bd.get('needs_review','—')}")
        self._total_lbl.setText(f"Total:   {bd.get('total_found','—')}")
