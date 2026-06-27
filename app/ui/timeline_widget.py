"""
TimelineWidget — Cache Explorer Timeline (Tier 3, Long-Term Vision feature).

Shows a monthly view of total cache size over time, derived from scan_history.
Also breaks down growth per ecosystem so the user can see exactly which tool
drove the increase.

Monthly view example:
    April    42 GB
    May      58 GB   +16 GB
    June    122 GB   +64 GB  ← "Ollama +42 GB, Cursor +12 GB, Docker +8 GB"
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from app.utils import fmt_bytes


_ECO_COLORS = {
    "Python":        "#3b82f6",
    "Node.js":       "#22c55e",
    "AI/ML":         "#f59e0b",
    "Docker":        "#0ea5e9",
    "System":        "#6b7280",
    "Build Systems": "#a78bfa",
}


def _month_key(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%Y-%m")
    except Exception:
        return "Unknown"


def _month_label(key: str) -> str:
    try:
        dt = datetime.strptime(key, "%Y-%m")
        return dt.strftime("%B %Y")
    except Exception:
        return key


class TimelineBarWidget(QWidget):
    """Single horizontal bar row for one month."""

    def __init__(self, label: str, size_bytes: int, max_bytes: int,
                 delta_bytes: int = 0, parent=None):
        super().__init__(parent)
        self._label  = label
        self._size   = size_bytes
        self._max    = max_bytes or 1
        self._delta  = delta_bytes
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h      = self.width(), self.height()
        label_w   = 120
        bar_start = label_w + 10
        bar_end   = w - 160
        bar_w     = max(bar_end - bar_start, 20)
        fill      = max(int(self._size / self._max * bar_w), 3)
        bar_h     = 20
        bar_y     = (h - bar_h) // 2

        font = QFont(); font.setPointSize(11); p.setFont(font)

        # Month label
        p.setPen(QColor("#9ca3af"))
        p.drawText(0, 0, label_w, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   self._label)

        # Bar background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1a1d22"))
        p.drawRoundedRect(bar_start, bar_y, bar_w, bar_h, 4, 4)

        # Bar fill — gradient-ish via solid colour
        p.setBrush(QColor("#1d4ed8"))
        p.drawRoundedRect(bar_start, bar_y, fill, bar_h, 4, 4)

        # Size label
        p.setPen(QColor("#e2e8f0"))
        font2 = QFont(); font2.setPointSize(11); font2.setBold(True); p.setFont(font2)
        p.drawText(bar_start + fill + 10, 0, 100, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   fmt_bytes(self._size))

        # Delta label
        if self._delta != 0:
            sign     = "▲" if self._delta > 0 else "▼"
            color    = "#f87171" if self._delta > 0 else "#4ade80"
            delta_s  = f"{sign} {fmt_bytes(abs(self._delta))}"
            font3 = QFont(); font3.setPointSize(10); p.setFont(font3)
            p.setPen(QColor(color))
            p.drawText(bar_start + fill + 100, 0, 120, h,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       delta_s)


class TimelineWidget(QWidget):
    """
    Full Cache Explorer Timeline view.
    Reads scan_history and scan_item_snapshots from the DB.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Cache Storage Timeline")
        title.setStyleSheet("font-size:15px; font-weight:700; color:#e2e8f0;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._refresh_btn = None  # placeholder
        outer.addLayout(hdr)

        desc = QLabel(
            "Monthly view of total cache size from your scan history. "
            "Run scans regularly to build up a useful history."
        )
        desc.setStyleSheet("color:#4b5563; font-size:12px;")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(sep)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_lyt = QVBoxLayout(self._content)
        self._content_lyt.setContentsMargins(0, 0, 0, 0)
        self._content_lyt.setSpacing(4)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, stretch=1)

        self.refresh()

    def refresh(self):
        # Clear content
        while self._content_lyt.count():
            child = self._content_lyt.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        data = self._load_timeline_data()

        if not data:
            empty = QLabel(
                "No timeline data yet.\n\n"
                "Run at least two scans over different days to see storage trends here."
            )
            empty.setStyleSheet("color:#374151; font-size:13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_lyt.addStretch()
            self._content_lyt.addWidget(empty)
            self._content_lyt.addStretch()
            return

        months  = sorted(data.keys())
        max_val = max(v["total"] for v in data.values()) or 1

        prev_total = 0
        for i, month in enumerate(months):
            entry = data[month]
            delta = entry["total"] - prev_total if i > 0 else 0

            # Month bar
            bar = TimelineBarWidget(
                label=_month_label(month),
                size_bytes=entry["total"],
                max_bytes=max_val,
                delta_bytes=delta,
            )
            self._content_lyt.addWidget(bar)

            # Ecosystem breakdown for months where we have snapshot data
            eco_breakdown = entry.get("by_ecosystem", {})
            if eco_breakdown and i > 0:
                eco_row = QHBoxLayout()
                eco_row.setContentsMargins(134, 0, 0, 8)
                eco_row.setSpacing(14)
                for eco, eco_bytes in sorted(eco_breakdown.items(), key=lambda x: -x[1])[:4]:
                    color = _ECO_COLORS.get(eco, "#6b7280")
                    lbl   = QLabel(f"● {eco}: {fmt_bytes(eco_bytes)}")
                    lbl.setStyleSheet(f"color:{color}; font-size:11px;")
                    eco_row.addWidget(lbl)
                eco_row.addStretch()
                eco_w = QWidget()
                eco_w.setLayout(eco_row)
                self._content_lyt.addWidget(eco_w)

            prev_total = entry["total"]

        self._content_lyt.addStretch()

    def _load_timeline_data(self) -> dict:
        """
        Load scan history and aggregate by month.
        Returns {YYYY-MM: {total: int, by_ecosystem: {eco: bytes}}}
        """
        try:
            from app.database.db import get_connection
            conn = get_connection()

            # Get scan history
            scans = conn.execute(
                "SELECT id, scanned_at, total_bytes FROM scan_history ORDER BY scanned_at"
            ).fetchall()

            if not scans:
                return {}

            # Try to get per-ecosystem data from snapshots
            try:
                snapshots = conn.execute(
                    "SELECT scan_id, ecosystem, SUM(size_bytes) as eco_bytes "
                    "FROM scan_item_snapshots GROUP BY scan_id, ecosystem"
                ).fetchall()
                snap_map = defaultdict(dict)
                for row in snapshots:
                    snap_map[row["scan_id"]][row["ecosystem"]] = row["eco_bytes"]
            except Exception:
                snap_map = {}

            # Aggregate by month — keep the LAST scan of each month
            monthly = {}
            for scan in scans:
                key   = _month_key(scan["scanned_at"])
                total = scan["total_bytes"] or 0
                if key not in monthly or total > monthly[key]["total"]:
                    monthly[key] = {
                        "total":        total,
                        "by_ecosystem": dict(snap_map.get(scan["id"], {})),
                    }

            return monthly

        except Exception:
            return {}
