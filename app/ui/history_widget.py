"""
HistoryWidget (v4)

Features
--------
* Two-tab interface: "Cleanup History" and "Pre-Clean Backups"
* Cleanups Tab:
  - Table showing Cache, Reclaimed bytes, Command run, Status, and Date.
  - Export cleanup history to CSV.
  - Aggregate statistics summary bar (Total reclaimed, Operations, Success rate).
* Backups Tab:
  - Table showing Cache, Files count, Original path, Backup location, Trigger, and Date.
  - Interactive "Open Folder" button and row double-click to reveal archive in explorer.
  - "Open Backups Root" quick-action button.
* Empty states with informative icons and guidance.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTableWidget,
    QVBoxLayout, QWidget, QTabWidget,
)
import qtawesome as qta

from app.ui.palettes import NEUTRAL, SEMANTIC, FONT_MONO
from app.database import get_cleanup_history, get_backup_history
from app.utils import fmt_bytes, open_in_explorer


def _fmt(b: int) -> str:
    return fmt_bytes(b)


class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cleanup_records: list = []
        self._backup_records: list = []
        self._init_ui()

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(24, 20, 24, 24)
        lyt.setSpacing(14)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_cleanup_tab(), "Cleanups")
        self._tabs.addTab(self._build_backup_tab(), "Backups")
        lyt.addWidget(self._tabs)

        # Initial state
        self._set_cleanup_empty(True)
        self._set_backup_empty(True)

    # ══════════════════════════════════════════════════════ CLEANUP TAB ══════

    def _build_cleanup_tab(self) -> QWidget:
        tab = QWidget()
        lyt = QVBoxLayout(tab)
        lyt.setContentsMargins(0, 12, 0, 0)
        lyt.setSpacing(14)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Cleanup History")
        title.setObjectName("sectionLabel")
        hdr.addWidget(title)
        hdr.addStretch()

        self._cleanup_export_btn = QPushButton("⬇  Export")
        self._cleanup_export_btn.setFixedHeight(28)
        self._cleanup_export_btn.setToolTip("Export cleanup history to CSV")
        self._cleanup_export_btn.clicked.connect(self._export_cleanups)
        self._cleanup_export_btn.setVisible(False)
        hdr.addWidget(self._cleanup_export_btn)

        self._cleanup_total_lbl = QLabel("")
        self._cleanup_total_lbl.setStyleSheet(f"color:{SEMANTIC['success']}; font-size:12px; font-weight:600;")
        hdr.addWidget(self._cleanup_total_lbl)
        lyt.addLayout(hdr)

        # ── empty state ───────────────────────────────────────────────────────
        self._cleanup_empty_w = QWidget()
        ev = QVBoxLayout(self._cleanup_empty_w)
        ev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.setSpacing(8)
        icon = QLabel("🕐")
        icon.setStyleSheet("font-size:36px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg  = QLabel("No cleanup history yet")
        msg.setStyleSheet(f'color:{NEUTRAL["text_faint"]}; font-size:14px; font-weight:500;')
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub  = QLabel("Scan your system and clean caches to see execution logs here.")
        sub.setStyleSheet("color:#4b5563; font-size:12px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(icon); ev.addWidget(msg); ev.addWidget(sub)
        lyt.addWidget(self._cleanup_empty_w)

        # ── table ─────────────────────────────────────────────────────────────
        self._cleanup_table = QTableWidget(0, 5)
        self._cleanup_table.setHorizontalHeaderLabels(
            ["Cache", "Reclaimed", "Command", "Status", "Date"]
        )
        hh = self._cleanup_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); hh.resizeSection(1, 100)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); hh.resizeSection(2, 200)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed); hh.resizeSection(3, 85)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed); hh.resizeSection(4, 155)
        self._cleanup_table.verticalHeader().setVisible(False)
        self._cleanup_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._cleanup_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._cleanup_table.setAlternatingRowColors(True)
        self._cleanup_table.setShowGrid(False)
        lyt.addWidget(self._cleanup_table)

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

        return tab

    # ══════════════════════════════════════════════════════ BACKUP TAB ═══════

    def _build_backup_tab(self) -> QWidget:
        tab = QWidget()
        lyt = QVBoxLayout(tab)
        lyt.setContentsMargins(0, 12, 0, 0)
        lyt.setSpacing(14)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Pre-Clean Backup Archives")
        title.setObjectName("sectionLabel")
        hdr.addWidget(title)
        hdr.addStretch()

        self._open_backup_root_btn = QPushButton("Open Backups Folder")
        self._open_backup_root_btn.setIcon(qta.icon("fa5s.folder-open", color=NEUTRAL["text_muted"]))
        self._open_backup_root_btn.setFixedHeight(28)
        self._open_backup_root_btn.setToolTip("Open the root backup directory in system file explorer")
        self._open_backup_root_btn.clicked.connect(self._open_backups_root)
        hdr.addWidget(self._open_backup_root_btn)

        self._backup_count_lbl = QLabel("")
        self._backup_count_lbl.setStyleSheet(f"color:{NEUTRAL['text_secondary']}; font-size:12px; font-weight:600;")
        hdr.addWidget(self._backup_count_lbl)
        lyt.addLayout(hdr)

        # ── empty state ───────────────────────────────────────────────────────
        self._backup_empty_w = QWidget()
        ev = QVBoxLayout(self._backup_empty_w)
        ev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.setSpacing(8)
        icon = QLabel("🛡️")
        icon.setStyleSheet("font-size:36px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg  = QLabel("No pre-clean backups recorded")
        msg.setStyleSheet(f'color:{NEUTRAL["text_faint"]}; font-size:14px; font-weight:500;')
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub  = QLabel("When configuration files are backed up before cleaning, archives will appear here.")
        sub.setStyleSheet("color:#4b5563; font-size:12px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(icon); ev.addWidget(msg); ev.addWidget(sub)
        lyt.addWidget(self._backup_empty_w)

        # ── table ─────────────────────────────────────────────────────────────
        self._backup_table = QTableWidget(0, 6)
        self._backup_table.setHorizontalHeaderLabels(
            ["Cache Name", "Files", "Original Path", "Trigger", "Date", "Action"]
        )
        hh = self._backup_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed);   hh.resizeSection(0, 160)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed);   hh.resizeSection(1, 70)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed);   hh.resizeSection(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed);   hh.resizeSection(4, 150)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed);   hh.resizeSection(5, 100)
        self._backup_table.verticalHeader().setVisible(False)
        self._backup_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._backup_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._backup_table.setAlternatingRowColors(True)
        self._backup_table.setShowGrid(False)
        self._backup_table.cellDoubleClicked.connect(self._on_backup_row_double_clicked)
        lyt.addWidget(self._backup_table)

        return tab

    # ── public API ────────────────────────────────────────────────────────────

    def refresh(self):
        # Refresh cleanups
        self._cleanup_records = get_cleanup_history(limit=500)
        if not self._cleanup_records:
            self._set_cleanup_empty(True)
        else:
            self._set_cleanup_empty(False)
            self._populate_cleanups()
            self._update_cleanup_stats()

        # Refresh backups
        self._backup_records = get_backup_history(limit=100)
        if not self._backup_records:
            self._set_backup_empty(True)
        else:
            self._set_backup_empty(False)
            self._populate_backups()

    # ── internal: cleanups ────────────────────────────────────────────────────

    def _set_cleanup_empty(self, empty: bool):
        self._cleanup_empty_w.setVisible(empty)
        self._cleanup_table.setVisible(not empty)
        self._stats_bar.setVisible(not empty)
        self._cleanup_export_btn.setVisible(not empty)
        if empty:
            self._cleanup_total_lbl.setText("")

    def _populate_cleanups(self):
        self._cleanup_table.setUpdatesEnabled(False)
        self._cleanup_table.setRowCount(0)

        for rec in self._cleanup_records:
            row     = self._cleanup_table.rowCount()
            success = bool(rec.get("success", 1))
            self._cleanup_table.insertRow(row)
            self._cleanup_table.setRowHeight(row, 38)

            # col 0 — cache name
            self._cleanup_table.setCellWidget(row, 0, self._cell(
                rec.get("cache_name", "Unknown"), NEUTRAL["text_primary"], bold=True
            ))

            # col 1 — reclaimed
            reclaimed = rec.get("bytes_reclaimed", 0)
            self._cleanup_table.setCellWidget(row, 1, self._cell(
                _fmt(reclaimed) if (success and reclaimed) else "—",
                SEMANTIC["success"] if success else NEUTRAL["text_muted"],
            ))

            # col 2 — command (truncated)
            cmd_raw    = rec.get("command") or ""
            first_line = cmd_raw.splitlines()[0] if cmd_raw.strip() else ""
            cmd        = (first_line[:40] + "…") if len(first_line) > 40 else first_line
            self._cleanup_table.setCellWidget(row, 2, self._cell(cmd or "—", NEUTRAL["text_muted"], mono=True))

            # col 3 — status badge
            self._cleanup_table.setCellWidget(row, 3, self._cell(
                "✓  Done" if success else "✗  Failed",
                SEMANTIC["success"] if success else SEMANTIC["danger"],
                bold=True,
            ))

            # col 4 — date
            raw = rec.get("cleaned_at", "")
            try:
                dt      = datetime.fromisoformat(raw)
                ds      = dt.strftime("%b %d %Y  %H:%M")
            except Exception:
                ds = raw[:19] if raw else "—"
            self._cleanup_table.setCellWidget(row, 4, self._cell(ds, "#4b5563"))

        self._cleanup_table.setUpdatesEnabled(True)

    def _update_cleanup_stats(self):
        total_bytes = sum(
            r.get("bytes_reclaimed", 0)
            for r in self._cleanup_records if r.get("success", 1)
        )
        ops     = len(self._cleanup_records)
        ok      = sum(1 for r in self._cleanup_records if r.get("success", 1))
        rate    = f"{ok/ops*100:.0f}%" if ops else "—"

        self._set_stat(self._stat_total, _fmt(total_bytes))
        self._set_stat(self._stat_ops,   str(ops))
        self._set_stat(self._stat_rate,  rate)
        self._cleanup_total_lbl.setText(f"All-time: {_fmt(total_bytes)}")

    def _export_cleanups(self):
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
                for r in self._cleanup_records:
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

    # ── internal: backups ─────────────────────────────────────────────────────

    def _set_backup_empty(self, empty: bool):
        self._backup_empty_w.setVisible(empty)
        self._backup_table.setVisible(not empty)
        if empty:
            self._backup_count_lbl.setText("")

    def _populate_backups(self):
        self._backup_table.setUpdatesEnabled(False)
        self._backup_table.setRowCount(0)

        for rec in self._backup_records:
            row        = self._backup_table.rowCount()
            b_dir      = rec.get("backup_dir", "")
            file_count = rec.get("file_count", 0)
            self._backup_table.insertRow(row)
            self._backup_table.setRowHeight(row, 38)

            # col 0 — cache name
            self._backup_table.setCellWidget(row, 0, self._cell(
                rec.get("cache_name", "Unknown"), NEUTRAL["text_primary"], bold=True
            ))

            # col 1 — files count
            self._backup_table.setCellWidget(row, 1, self._cell(
                f"{file_count} files", SEMANTIC["warning"]
            ))

            # col 2 — original path
            orig_path = rec.get("cache_path", "")
            self._backup_table.setCellWidget(row, 2, self._cell(orig_path, NEUTRAL["text_secondary"], mono=True))

            # col 3 — trigger
            trigger = rec.get("trigger", "pre_clean")
            self._backup_table.setCellWidget(row, 3, self._cell(trigger, NEUTRAL["text_muted"]))

            # col 4 — date
            raw = rec.get("backed_up_at", "")
            try:
                dt = datetime.fromisoformat(raw)
                ds = dt.strftime("%b %d %Y  %H:%M")
            except Exception:
                ds = raw[:19] if raw else "—"
            self._backup_table.setCellWidget(row, 4, self._cell(ds, "#4b5563"))

            # col 5 — action button
            btn_w = QWidget()
            bl = QHBoxLayout(btn_w)
            bl.setContentsMargins(6, 4, 6, 4)
            btn = QPushButton("Open")
            btn.setFixedHeight(24)
            btn.setToolTip(f"Open {b_dir} in explorer")
            btn.clicked.connect(lambda _, d=b_dir: open_in_explorer(d))
            bl.addWidget(btn)
            self._backup_table.setCellWidget(row, 5, btn_w)

        self._backup_count_lbl.setText(f"{len(self._backup_records)} archive(s)")
        self._backup_table.setUpdatesEnabled(True)

    def _open_backups_root(self):
        root = Path.home() / ".devcache_guardian" / "backups"
        root.mkdir(parents=True, exist_ok=True)
        open_in_explorer(str(root))

    def _on_backup_row_double_clicked(self, row: int, _col: int):
        if 0 <= row < len(self._backup_records):
            b_dir = self._backup_records[row].get("backup_dir")
            if b_dir:
                open_in_explorer(b_dir)

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
        if mono:  style += f" font-family:{FONT_MONO}; font-size:11px;"
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
        lbl.setStyleSheet(f'font-size:10px; color:{NEUTRAL["text_faint"]}; letter-spacing:0.4px;')
        val = QLabel(value)
        val.setStyleSheet(f'font-size:15px; font-weight:700; color:{NEUTRAL["text_primary"]}; font-family:{FONT_MONO};')
        val.setObjectName("_stat_val")
        vl.addWidget(lbl); vl.addWidget(val)
        return w

    @staticmethod
    def _set_stat(widget: QWidget, value: str):
        for child in widget.findChildren(QLabel):
            if child.objectName() == "_stat_val":
                child.setText(value)
                return
