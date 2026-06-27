"""
HistoryWidget (v3)

Improvements
------------
* Empty state now shows an icon-style placeholder with helpful text.
* Added "Export history" button that saves to CSV.
* Command column shows the actual command run, truncated cleanly.
* Failure rows are highlighted with a subtle red tint.
* Statistics summary bar at the bottom (total cleaned, success rate).
"""
from __future__ import annotations

import csv
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTableWidget,
    QVBoxLayout, QWidget,
)

from app.database import get_cleanup_history
from app.utils import fmt_bytes


def _fmt(b: int) -> str:
    return fmt_bytes(b)


class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list = []
        self._init_ui()

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(24, 20, 24, 24)
        lyt.setSpacing(14)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Cleanup History")
        title.setStyleSheet("font-size:13px; font-weight:600; color:#9ca3af;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._export_btn = QPushButton("⬇  Export")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setToolTip("Export cleanup history to CSV")
        self._export_btn.clicked.connect(self._export)
        self._export_btn.setVisible(False)
        hdr.addWidget(self._export_btn)

        self._total_lbl = QLabel("")
        self._total_lbl.setStyleSheet("color:#4ade80; font-size:12px; font-weight:600;")
        hdr.addWidget(self._total_lbl)
        lyt.addLayout(hdr)

        # ── empty state ───────────────────────────────────────────────────────
        self._empty_w = QWidget()
        ev = QVBoxLayout(self._empty_w)
        ev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.setSpacing(8)
        icon = QLabel("🕐")
        icon.setStyleSheet("font-size:36px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg  = QLabel("No cleanup history yet")
        msg.setStyleSheet("color:#374151; font-size:14px; font-weight:500;")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub  = QLabel("Scan your system and clean some caches to see the history here.")
        sub.setStyleSheet("color:#1f2937; font-size:12px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(icon); ev.addWidget(msg); ev.addWidget(sub)
        lyt.addWidget(self._empty_w)

        # ── table ─────────────────────────────────────────────────────────────
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Cache", "Reclaimed", "Command", "Status", "Date"]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); hh.resizeSection(1, 100)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); hh.resizeSection(2, 200)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed); hh.resizeSection(3, 80)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed); hh.resizeSection(4, 155)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        lyt.addWidget(self._table)

        # ── stats bar ─────────────────────────────────────────────────────────
        self._stats_bar = QWidget()
        self._stats_bar.setStyleSheet(
            "background:#13151a; border:1px solid #1e2025; border-radius:6px;"
        )
        sb = QHBoxLayout(self._stats_bar)
        sb.setContentsMargins(16, 8, 16, 8); sb.setSpacing(24)
        self._stat_total = self._stat_widget("Total reclaimed", "—")
        self._stat_ops   = self._stat_widget("Operations", "—")
        self._stat_rate  = self._stat_widget("Success rate", "—")
        sb.addWidget(self._stat_total)
        sb.addWidget(self._stat_ops)
        sb.addWidget(self._stat_rate)
        sb.addStretch()
        lyt.addWidget(self._stats_bar)

        # Initial state
        self._set_empty(True)

    # ── public ────────────────────────────────────────────────────────────────

    def refresh(self):
        self._records = get_cleanup_history(limit=500)
        if not self._records:
            self._set_empty(True)
            return
        self._set_empty(False)
        self._populate()
        self._update_stats()

    # ── internal ──────────────────────────────────────────────────────────────

    def _set_empty(self, empty: bool):
        self._empty_w.setVisible(empty)
        self._table.setVisible(not empty)
        self._stats_bar.setVisible(not empty)
        self._export_btn.setVisible(not empty)
        if empty:
            self._total_lbl.setText("")

    def _populate(self):
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(0)

        for rec in self._records:
            row     = self._table.rowCount()
            success = bool(rec.get("success", 1))
            self._table.insertRow(row)
            self._table.setRowHeight(row, 38)

            # col 0 — cache name
            self._table.setCellWidget(row, 0, self._cell(
                rec.get("cache_name", "Unknown"), "#e2e8f0", bold=True
            ))

            # col 1 — reclaimed
            reclaimed = rec.get("bytes_reclaimed", 0)
            self._table.setCellWidget(row, 1, self._cell(
                _fmt(reclaimed) if (success and reclaimed) else "—",
                "#4ade80" if success else "#6b7280",
            ))

            # col 2 — command (truncated)
            cmd_raw    = rec.get("command") or ""
            first_line = cmd_raw.splitlines()[0] if cmd_raw.strip() else ""
            cmd        = (first_line[:40] + "…") if len(first_line) > 40 else first_line
            self._table.setCellWidget(row, 2, self._cell(cmd or "—", "#6b7280", mono=True))

            # col 3 — status badge
            self._table.setCellWidget(row, 3, self._cell(
                "✓  Done" if success else "✗  Failed",
                "#4ade80" if success else "#f87171",
                bold=True,
            ))

            # col 4 — date
            raw = rec.get("cleaned_at", "")
            try:
                dt      = datetime.fromisoformat(raw)
                ds      = dt.strftime("%b %d %Y  %H:%M")
            except Exception:
                ds = raw[:19] if raw else "—"
            self._table.setCellWidget(row, 4, self._cell(ds, "#4b5563"))

        self._table.setUpdatesEnabled(True)

    def _update_stats(self):
        total_bytes = sum(
            r.get("bytes_reclaimed", 0)
            for r in self._records if r.get("success", 1)
        )
        ops     = len(self._records)
        ok      = sum(1 for r in self._records if r.get("success", 1))
        rate    = f"{ok/ops*100:.0f}%" if ops else "—"

        self._set_stat(self._stat_total, _fmt(total_bytes))
        self._set_stat(self._stat_ops,   str(ops))
        self._set_stat(self._stat_rate,  rate)
        self._total_lbl.setText(f"All-time: {_fmt(total_bytes)}")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export cleanup history", "cleanup_history.csv",
            "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Cache", "Reclaimed (bytes)", "Reclaimed (human)",
                             "Command", "Method", "Status", "Date"])
                for r in self._records:
                    w.writerow([
                        r.get("cache_name", ""),
                        r.get("bytes_reclaimed", 0),
                        _fmt(r.get("bytes_reclaimed", 0)),
                        r.get("command", ""),
                        r.get("method", ""),
                        "success" if r.get("success", 1) else "failed",
                        r.get("cleaned_at", ""),
                    ])
        except Exception as exc:
            from loguru import logger
            logger.error(f"History export failed: {exc}")

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _cell(text: str, color: str,
              bold: bool = False, mono: bool = False) -> QWidget:
        w   = QWidget()
        lyt = QHBoxLayout(w)
        lyt.setContentsMargins(10, 0, 6, 0)
        lbl = QLabel(text)
        style = f"color:{color}; font-size:12px;"
        if bold:  style += " font-weight:600;"
        if mono:  style += " font-family:'Cascadia Code','Consolas',monospace;"
        lbl.setStyleSheet(style)
        lyt.addWidget(lbl)
        lyt.addStretch()
        return w

    @staticmethod
    def _stat_widget(label: str, value: str) -> QWidget:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet("font-size:10px; color:#374151; letter-spacing:0.4px;")
        val = QLabel(value)
        val.setStyleSheet("font-size:15px; font-weight:700; color:#e2e8f0;")
        val.setObjectName("_stat_val")
        vl.addWidget(lbl); vl.addWidget(val)
        return w

    @staticmethod
    def _set_stat(widget: QWidget, value: str):
        for child in widget.findChildren(QLabel):
            if child.objectName() == "_stat_val":
                child.setText(value)
                return
