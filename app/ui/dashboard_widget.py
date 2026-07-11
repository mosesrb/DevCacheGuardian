"""
DashboardWidget (v6) — Developer Storage Intelligence Platform

New sections
------------
1. Health Score gauge  (top-left metric)
2. Cache Growth Alerts (delta between last 2 scans — "Ollama grew 32 GB")
3. Space Trend chart   (sparkline of last 14 scans)
4. Storage breakdown   (horizontal bars)
5. Largest caches list
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from app.models import CacheItem, RiskLevel
from app.utils import fmt_bytes as _fmt
from .health_score_widget import HealthScoreWidget
from app.ui.eco_colors import eco_color
from app.ui.theme import theme_manager
from app.ui.palettes import NEUTRAL, SEMANTIC, FONT_MONO

_RISK_COLORS = {
    RiskLevel.SAFE:   SEMANTIC["success"],
    RiskLevel.REVIEW: SEMANTIC["warning"],
    RiskLevel.DANGER: SEMANTIC["danger"],
}
_LABEL_W   = 170
_RIGHT_PAD = 90
_MARGIN_L  = 16


# ── mini-bar chart ────────────────────────────────────────────────────────────

class MiniBarWidget(QWidget):
    def __init__(self, items: List[CacheItem], parent=None):
        super().__init__(parent)
        self.items = sorted(items, key=lambda x: -x.size_bytes)[:10]
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(max(40, len(self.items) * 36 + 16))

    def resizeEvent(self, e): super().resizeEvent(e); self.update()

    def paintEvent(self, _):
        if not self.items: return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total     = sum(i.size_bytes for i in self.items) or 1
        bar_x     = _MARGIN_L + _LABEL_W
        available = max(self.width() - bar_x - _RIGHT_PAD - _MARGIN_L, 20)
        bar_h, row_h, y = 16, 36, 8
        font = QFont(); font.setPointSize(10); p.setFont(font)
        for item in self.items:
            fill  = max(int(item.size_bytes / total * available), 2)
            color = eco_color(item.ecosystem)
            p.setPen(QColor(NEUTRAL["text_secondary"]))
            name = item.name[:24] + "…" if len(item.name) > 24 else item.name
            p.drawText(_MARGIN_L, y, _LABEL_W - 6, row_h,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(NEUTRAL["bg_card"]))
            p.drawRoundedRect(bar_x, y + (row_h - bar_h) // 2, available, bar_h, 4, 4)
            p.setBrush(QColor(color))
            p.drawRoundedRect(bar_x, y + (row_h - bar_h) // 2, fill, bar_h, 4, 4)
            dot_x = bar_x + available + 8
            dot_y = y + (row_h - 8) // 2
            p.setBrush(QColor(_RISK_COLORS.get(item.risk_level, NEUTRAL["text_muted"])))
            p.drawEllipse(dot_x, dot_y, 8, 8)
            p.setPen(QColor(NEUTRAL["text_muted"]))
            p.drawText(dot_x + 14, y, _RIGHT_PAD - 22, row_h,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       item.size_label)
            y += row_h


# ── trend sparkline ───────────────────────────────────────────────────────────

class TrendChartWidget(QWidget):
    def __init__(self, records: list, parent=None):
        super().__init__(parent)
        self._records = records
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _):
        if not self._records:
            p = QPainter(self); p.setPen(QColor(NEUTRAL["text_faint"]))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No trend data yet — run more scans")
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mx = max((r.get("total_bytes") or 0) for r in self._records) or 1
        n, w, h = len(self._records), self.width(), self.height()
        px, py  = 8, 12
        bar_w   = max(4, (w - 2*px) // n - 3)
        gap     = (w - 2*px - n*bar_w) // max(n-1, 1)
        x = px
        for i, rec in enumerate(self._records):
            val   = rec.get("total_bytes") or 0
            bh    = max(3, int(val / mx * (h - py*2)))
            by    = h - py - bh
            pal = theme_manager.current_palette()
            color = pal["accent_text"] if i == len(self._records)-1 else pal["accent"]
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
            p.drawRoundedRect(x, by, bar_w, bh, 2, 2)
            x += bar_w + gap
        if self._records:
            p.setPen(QColor(NEUTRAL["text_faint"]))
            f = QFont(); f.setPointSize(9); p.setFont(f)
            try:
                d0 = datetime.fromisoformat(self._records[0]["scanned_at"]).strftime("%b %d")
                dl = datetime.fromisoformat(self._records[-1]["scanned_at"]).strftime("%b %d")
                p.drawText(px, h-2, d0)
                fm = p.fontMetrics()
                p.drawText(w - px - fm.horizontalAdvance(dl), h-2, dl)
            except Exception: pass
            p.drawText(px, py+2, _fmt(mx))


# ── metric card ───────────────────────────────────────────────────────────────

class MetricCard(QWidget):
    def __init__(self, label, value, sub="", color=NEUTRAL["text_primary"], parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard"); self.setMinimumHeight(96)
        lyt = QVBoxLayout(self); lyt.setContentsMargins(16,14,16,14); lyt.setSpacing(4)
        lbl = QLabel(label.upper()); lbl.setObjectName("metricLabel"); lyt.addWidget(lbl)
        val = QLabel(value); val.setObjectName("metricValue")
        val.setStyleSheet(f"color:{color};"); lyt.addWidget(val)
        if sub:
            s = QLabel(sub); s.setObjectName("metricSub"); lyt.addWidget(s)


# ── growth alert card ─────────────────────────────────────────────────────────

class GrowthAlertWidget(QWidget):
    """Surfaces top cache growth changes between last two scans."""

    def __init__(self, deltas: list, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background:#1c0a00; border:1px solid #451a03; border-radius:8px;"
        )
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(14, 12, 14, 12)
        lyt.setSpacing(8)

        hdr = QLabel("⚠  Cache growth detected since last scan")
        hdr.setStyleSheet(f"font-size:12px; font-weight:600; color:{SEMANTIC['warning']};")
        lyt.addWidget(hdr)

        # Show top 4 growers
        growers = [d for d in deltas if (d.get("delta_bytes") or 0) > 1024*1024*10]
        growers = sorted(growers, key=lambda x: -(x.get("delta_bytes") or 0))[:4]

        for g in growers:
            delta   = g.get("delta_bytes", 0) or 0
            name    = g.get("cache_name", "Unknown")
            eco     = g.get("ecosystem", "")
            eco_c   = eco_color(eco)
            row     = QHBoxLayout()
            n_lbl   = QLabel(f"▲  {name}")
            n_lbl.setStyleSheet("color:#fde68a; font-size:12px;")
            d_lbl   = QLabel(f"+{_fmt(delta)}")
            d_lbl.setStyleSheet("color:#f97316; font-size:12px; font-weight:600;")
            row.addWidget(n_lbl); row.addStretch(); row.addWidget(d_lbl)
            lyt.addLayout(row)


# ── dashboard ─────────────────────────────────────────────────────────────────

class DashboardWidget(QWidget):
    clean_safe_requested = Signal()
    export_report_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[CacheItem]  = []
        self._health: dict            = {}
        self._growth_deltas: list     = []
        self._session_cleaned: int    = 0
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content = QWidget()
        self._layout  = QVBoxLayout(self._content)
        self._layout.setContentsMargins(24,20,24,24); self._layout.setSpacing(20)
        self._layout.addStretch()
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll)

    def update_items(self, items: List[CacheItem]):
        self._items = items
        # Compute health score
        try:
            from app.services.scoring import get_health_score
            self._health = get_health_score(items)
        except Exception:
            self._health = {"score": 0, "grade": "?", "breakdown": {}}
        self._rebuild()

    def update_growth(self, deltas: list):
        self._growth_deltas = deltas
        self._rebuild()

    def add_session_cleaned(self, n: int):
        self._session_cleaned += n
        self._rebuild()

    def _rebuild(self):
        new_content = QWidget()
        lyt         = QVBoxLayout(new_content)
        lyt.setContentsMargins(24, 20, 24, 24); lyt.setSpacing(20)
        items = self._items

        if not items:
            empty = QLabel("Run a scan to see your storage intelligence report")
            empty.setObjectName("mutedText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lyt.addStretch(); lyt.addWidget(empty); lyt.addStretch()
            self._scroll.setWidget(new_content); self._content = new_content; return

        total   = sum(i.size_bytes for i in items)
        safe    = sum(i.size_bytes for i in items if i.risk_level == RiskLevel.SAFE)
        review  = sum(i.size_bytes for i in items if i.risk_level == RiskLevel.REVIEW)
        danger  = sum(1 for i in items if i.risk_level == RiskLevel.DANGER)

        # ── row 1: health score + 4 metric cards ─────────────────────────────
        mrow = QHBoxLayout(); mrow.setSpacing(12)

        self._health_card = HealthScoreWidget()
        self._health_card.update_health(self._health)
        mrow.addWidget(self._health_card)

        mrow.addWidget(MetricCard("Total found",     _fmt(total),    f"{len(items)} locations"))
        mrow.addWidget(MetricCard("Safe to reclaim", _fmt(safe),     "no project risk",   theme_manager.current_palette()["accent_text"]))
        mrow.addWidget(MetricCard("Needs review",    _fmt(review),   "re-downloadable",   SEMANTIC["warning"]))
        mrow.addWidget(MetricCard("Cleaned today",
            _fmt(self._session_cleaned) if self._session_cleaned else "—",
            "this session", SEMANTIC["success"]))
        lyt.addLayout(mrow)

        # ── row 2: action buttons ─────────────────────────────────────────────
        ar = QHBoxLayout(); ar.setSpacing(10)
        clean_btn = QPushButton("🧹  Clean all safe items")
        clean_btn.setObjectName("btnPrimary"); clean_btn.setFixedHeight(32)
        clean_btn.clicked.connect(self.clean_safe_requested)
        ar.addWidget(clean_btn)
        report_btn = QPushButton("📄  Export report")
        report_btn.setFixedHeight(32)
        report_btn.setToolTip("Export a full HTML audit report")
        report_btn.clicked.connect(self.export_report_requested)
        ar.addWidget(report_btn)
        ar.addStretch()
        lyt.addLayout(ar)

        # ── growth alerts (only if deltas exist) ──────────────────────────────
        growers = [d for d in self._growth_deltas
                   if (d.get("delta_bytes") or 0) > 1024*1024*50]
        if growers:
            lyt.addWidget(GrowthAlertWidget(self._growth_deltas))

        # ── storage heatmap / bar chart ───────────────────────────────────────
        lyt.addWidget(self._section("Storage breakdown"))
        lyt.addWidget(MiniBarWidget(items))
        legend = QHBoxLayout(); legend.setSpacing(18)
        from app.ui.eco_colors import ECO_COLORS as _ECO_COLORS
        for eco, color in _ECO_COLORS.items():
            dot = QLabel(f"● {eco}")
            dot.setStyleSheet(f"color:{color}; font-size:11px;")
            legend.addWidget(dot)
        legend.addStretch(); lyt.addLayout(legend)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); lyt.addWidget(sep)

        # ── space trend ───────────────────────────────────────────────────────
        lyt.addWidget(self._section("Space found over time"))
        try:
            from app.database import get_scan_trend
            trend_data = get_scan_trend(14)
        except Exception:
            trend_data = []
        lyt.addWidget(TrendChartWidget(trend_data))

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine); lyt.addWidget(sep2)

        # ── top caches ────────────────────────────────────────────────────────
        lyt.addWidget(self._section("Largest caches"))
        for item in sorted(items, key=lambda x: -x.size_bytes)[:6]:
            row_w  = QWidget()
            row_lyt = QHBoxLayout(row_w)
            row_lyt.setContentsMargins(0, 2, 0, 2)
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{_RISK_COLORS[item.risk_level]}; font-size:10px;")
            dot.setFixedWidth(14)
            row_lyt.addWidget(dot)
            name_lbl = QLabel(item.name)
            name_lbl.setStyleSheet(f'color:{NEUTRAL["text_primary"]}; font-size:13px;')
            row_lyt.addWidget(name_lbl)
            eco_lbl = QLabel(item.ecosystem)
            eco_lbl.setStyleSheet(f"color:{eco_color(item.ecosystem)}; font-size:11px;")
            row_lyt.addWidget(eco_lbl); row_lyt.addStretch()
            size_lbl = QLabel(item.size_label)
            size_lbl.setStyleSheet(f'color:{NEUTRAL["text_primary"]}; font-weight:600; font-size:13px;')
            row_lyt.addWidget(size_lbl)
            lyt.addWidget(row_w)

        lyt.addStretch()
        self._scroll.setWidget(new_content); self._content = new_content

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f'font-size:13px; font-weight:600; color:{NEUTRAL["text_secondary"]};')
        return lbl
