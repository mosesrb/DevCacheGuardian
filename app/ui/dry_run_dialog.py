"""
DryRunResultDialog — shows the results of a dry-run preflight check and lets
the user decide whether to proceed with the real cleanup or cancel.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from typing import List, Tuple

from app.models import CacheItem
from app.cleaners.cleaner_service import CleanResult
from app.utils import fmt_bytes as _fmt


class DryRunResultDialog(QDialog):
    """
    Presents dry-run check output for one or many items.

    result  : list of (CacheItem, CleanResult) pairs
    Returns : QDialog.Accepted  → user wants to proceed with real cleanup
              QDialog.Rejected  → user cancelled
    """

    def __init__(self,
                 results: List[Tuple[CacheItem, CleanResult]],
                 parent=None):
        super().__init__(parent)
        self._results = results
        self.setWindowTitle("Dry Run — Preflight Check")
        self.setMinimumWidth(520)
        self.setMinimumHeight(360)
        self.setModal(True)
        self._init_ui()

    # ── build ─────────────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Header
        all_ok = all(r.success for _, r in self._results)
        total_bytes = sum(r.bytes_reclaimed for _, r in self._results if r.success)

        icon  = "✓" if all_ok else "⚠"
        color = "#4ade80" if all_ok else "#fbbf24"
        title = QLabel(f"{icon}  Preflight check {'passed' if all_ok else 'completed with warnings'}")
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {color};")
        layout.addWidget(title)

        summary = QLabel(
            f"{len(self._results)} cache{'s' if len(self._results) != 1 else ''} checked  ·  "
            f"~{_fmt(total_bytes)} estimated reclaimable"
        )
        summary.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(summary)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Scrollable check output
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(14)

        for item, result in self._results:
            block = self._make_block(item, result)
            inner_layout.addWidget(block)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # Buttons
        note = QLabel(
            "No files were touched during this check."
            if all_ok else
            "Some checks reported issues — review before proceeding."
        )
        note.setStyleSheet("color: #4b5563; font-size: 11px;")
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        if all_ok:
            proceed_btn = QPushButton("Proceed with cleanup")
            proceed_btn.setObjectName("btnPrimary")
            proceed_btn.setFixedWidth(160)
            proceed_btn.clicked.connect(self.accept)
            btn_row.addWidget(proceed_btn)
        else:
            proceed_btn = QPushButton("Proceed anyway")
            proceed_btn.setObjectName("btnWarning")
            proceed_btn.setFixedWidth(130)
            proceed_btn.clicked.connect(self.accept)
            btn_row.addWidget(proceed_btn)

        layout.addLayout(btn_row)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _make_block(self, item: CacheItem, result: CleanResult) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            "background: #13151a; border: 1px solid #1e2025; border-radius: 8px;"
        )
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(6)

        # Item title row
        hdr = QHBoxLayout()
        name_lbl = QLabel(item.name)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #e2e8f0;")
        hdr.addWidget(name_lbl)
        hdr.addStretch()

        status_icon = "✓" if result.success else "✗"
        status_color = "#4ade80" if result.success else "#f87171"
        status_lbl = QLabel(f"{status_icon} {'Ready' if result.success else 'Issue'}")
        status_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {status_color};")
        hdr.addWidget(status_lbl)
        v.addLayout(hdr)

        # Check lines
        for line in result.checks:
            if not line.strip():
                v.addSpacing(2)
                continue
            line_lbl = QLabel(line)
            indent = line.startswith("  ")
            fg = "#6b7280" if indent else (
                "#4ade80" if line.startswith("✓")
                else "#f87171" if line.startswith("✗")
                else "#fbbf24" if line.startswith("⚠")
                else "#9ca3af"
            )
            line_lbl.setStyleSheet(
                f"color: {fg}; font-size: 12px;"
                f"{'padding-left: 14px;' if indent else ''}"
                f"{'font-family: monospace;' if '→' in line or ':' in line else ''}"
            )
            v.addWidget(line_lbl)

        # Protected files section (from content_warnings)
        if result.content_warnings:
            sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("background: #1e2025; margin-top: 4px;")
            v.addWidget(sep)
            hdr2 = QLabel("🛡  Files that will be preserved (not deleted):")
            hdr2.setStyleSheet("font-size: 11px; font-weight: 600; color: #fbbf24;")
            v.addWidget(hdr2)
            for cw in result.content_warnings:
                row = QHBoxLayout()
                il = QLabel(cw.icon); il.setFixedWidth(16)
                row.addWidget(il)
                pl = QLabel(cw.relative)
                pl.setStyleSheet(
                    f"color: {cw.severity_color}; font-size: 11px;"
                    "font-family: 'Cascadia Code','Consolas',monospace;"
                )
                row.addWidget(pl)
                row.addSpacing(6)
                dl = QLabel(cw.label)
                dl.setStyleSheet("color: #6b7280; font-size: 11px;")
                row.addWidget(dl)
                row.addStretch()
                rw = QWidget(); rw.setLayout(row)
                v.addWidget(rw)

        return w
