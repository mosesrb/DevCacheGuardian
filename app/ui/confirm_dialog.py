"""
ConfirmCleanDialog — shows what will be cleaned and lets the user run a
dry-run preflight check before committing.

v2: Pre-deletion content analysis runs synchronously when the dialog opens.
    If config/credential files are detected, a warning section is shown with
    a "Back up files now" button before the user can proceed.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QScrollArea
)
from PySide6.QtCore import Qt
from typing import List

from app.models import CacheItem, RiskLevel, CleanupMethod
from app.utils import fmt_bytes as _fmt
from app.services.content_analyzer import analyze_directory, ContentWarning, has_critical_warnings


class ConfirmCleanDialog(QDialog):
    """
    Shows a summary of what will be cleaned.

    Public attributes after exec():
      .requested_dry_run : bool   — True if user clicked "Dry run first"
      .backup_performed  : bool   — True if user backed up before cleaning
    """

    def __init__(self, items: List[CacheItem], parent=None):
        super().__init__(parent)
        self.items = items
        self.requested_dry_run = False
        self.backup_performed  = False
        self.setWindowTitle("Confirm cleanup")
        self.setMinimumWidth(500)
        self.setModal(True)

        # Run content analysis for DIRECTORY items
        self._all_warnings: List[ContentWarning] = []
        for item in items:
            if item.cleanup_method == CleanupMethod.DIRECTORY:
                self._all_warnings.extend(analyze_directory(item.path, item.id))

        self._init_ui()

    # ── build ─────────────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        is_bulk    = len(self.items) > 1
        total      = sum(i.size_bytes for i in self.items)
        has_review = any(i.risk_level == RiskLevel.REVIEW for i in self.items)

        # Title
        title_text = f"Clean {len(self.items)} caches?" if is_bulk \
                     else f"Clean {self.items[0].name}?"
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        layout.addWidget(title)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Content warning banner (shown if analysis found anything) ─────────
        if self._all_warnings:
            layout.addWidget(self._build_warning_banner())
            sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(sep2)

        # Space savings forecast bar
        layout.addWidget(self._forecast_bar(total))

        # Body text
        if is_bulk:
            body_text = (
                f"Runs the official cleanup command for each of the "
                f"{len(self.items)} selected caches.  "
                "Your virtual environments and project files will <b>not</b> be touched."
            )
        else:
            item = self.items[0]
            method = "running the cleanup command" if item.cleanup_command \
                     else "removing the cache directory"
            risk_note = (
                "<br><br><span style='color:#fbbf24;'>⚠ This cache may take time to rebuild.</span>"
                if item.risk_level == RiskLevel.REVIEW else ""
            )
            body_text = f"Reclaims <b>{item.size_label}</b> by {method}.{risk_note}"

        body = QLabel(body_text)
        body.setStyleSheet("color: #9ca3af; font-size: 13px; line-height: 1.6;")
        body.setWordWrap(True)
        layout.addWidget(body)

        # Command previews
        shown = self.items[:6]
        for item in shown:
            if item.cleanup_command:
                preview_text = item.cleanup_command.splitlines()[0]
            else:
                preview_text = f"Remove contents of  {item.path}"
            cmd_lbl = QLabel(preview_text)
            cmd_lbl.setStyleSheet(
                "font-family: 'Cascadia Code','Consolas',monospace; font-size: 11px;"
                "color: #93c5fd; background: #0d1117; border: 1px solid #1e2025;"
                "border-radius: 6px; padding: 6px 10px;"
            )
            cmd_lbl.setWordWrap(True)
            layout.addWidget(cmd_lbl)
        if len(self.items) > 6:
            more = QLabel(f"… and {len(self.items) - 6} more")
            more.setStyleSheet("color: #4b5563; font-size: 12px;")
            layout.addWidget(more)

        layout.addSpacing(4)

        # Buttons
        btn_row = QHBoxLayout()

        dry_run_btn = QPushButton("🔍  Dry run first")
        dry_run_btn.setToolTip(
            "Simulate the cleanup without deleting anything.\n"
            "Checks tool availability and estimates reclaimable space."
        )
        dry_run_btn.clicked.connect(self._on_dry_run)
        btn_row.addWidget(dry_run_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        label = "Clean now" if not has_review else "Clean anyway"
        obj   = "btnPrimary" if not has_review else "btnWarning"
        clean_btn = QPushButton(label)
        clean_btn.setObjectName(obj)
        clean_btn.setFixedWidth(120)
        clean_btn.clicked.connect(self.accept)
        btn_row.addWidget(clean_btn)

        layout.addLayout(btn_row)

    # ── Warning banner ────────────────────────────────────────────────────────

    def _build_warning_banner(self) -> QWidget:
        """Red/amber banner listing config files detected inside cache dirs."""
        has_crit = has_critical_warnings(self._all_warnings)
        border   = "#dc2626" if has_crit else "#d97706"
        bg       = "#1c0a0a" if has_crit else "#1c1305"
        icon     = "🔴" if has_crit else "⚠"
        severity_label = "Configuration & credential files detected" if has_crit \
                         else "Configuration files detected"

        banner = QWidget()
        banner.setStyleSheet(
            f"background: {bg}; border: 1px solid {border}; border-radius: 8px;"
        )
        v = QVBoxLayout(banner)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)

        hdr = QLabel(f"{icon}  {severity_label}")
        hdr.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {border};")
        v.addWidget(hdr)

        desc = QLabel(
            "The following files were found inside the selected cache directories.\n"
            "They will be <b>automatically preserved</b> — not deleted.\n"
            "We recommend backing them up before proceeding."
        )
        desc.setStyleSheet("color: #9ca3af; font-size: 12px;")
        desc.setWordWrap(True)
        v.addWidget(desc)

        # Scrollable file list (cap at 6 visible)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(130)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(3)

        for w in self._all_warnings:
            row = QHBoxLayout()
            icon_lbl = QLabel(w.icon)
            icon_lbl.setFixedWidth(18)
            row.addWidget(icon_lbl)
            path_lbl = QLabel(w.relative)
            path_lbl.setStyleSheet(
                f"color: {w.severity_color}; font-size: 11px;"
                "font-family: 'Cascadia Code','Consolas',monospace;"
            )
            row.addWidget(path_lbl)
            row.addSpacing(8)
            desc_lbl = QLabel(w.label)
            desc_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            row.addWidget(desc_lbl)
            row.addStretch()
            iw = QWidget(); iw.setLayout(row)
            iv.addWidget(iw)

        iv.addStretch()
        scroll.setWidget(inner)
        v.addWidget(scroll)

        # Backup button
        backup_row = QHBoxLayout()
        backup_btn = QPushButton("💾  Back up these files first")
        backup_btn.setObjectName("btnWarning")
        backup_btn.setToolTip(
            "Copies the listed files to ~/.devcache_guardian/backups/\n"
            "before any deletion takes place."
        )
        backup_btn.clicked.connect(self._on_backup_now)
        backup_row.addWidget(backup_btn)
        backup_row.addStretch()
        self._backup_btn = backup_btn
        v.addLayout(backup_row)

        return banner

    # ── space forecast widget ─────────────────────────────────────────────────

    def _forecast_bar(self, total_bytes: int) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            "background: #13151a; border: 1px solid #1e2025; border-radius: 8px;"
        )
        h = QHBoxLayout(w)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(20)

        def _stat(label: str, value: str, color: str) -> QWidget:
            sw = QWidget()
            sv = QVBoxLayout(sw)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(2)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet("font-size: 10px; color: #374151; letter-spacing: 0.5px;")
            val = QLabel(value)
            val.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {color};")
            sv.addWidget(lbl)
            sv.addWidget(val)
            return sw

        h.addWidget(_stat("Will reclaim", _fmt(total_bytes), "#4ade80"))

        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet("background: #1e2025;")
        h.addWidget(div)

        h.addWidget(_stat("Items", str(len(self.items)), "#e2e8f0"))

        div2 = QFrame(); div2.setFrameShape(QFrame.Shape.VLine)
        div2.setStyleSheet("background: #1e2025;")
        h.addWidget(div2)

        safe_count   = sum(1 for i in self.items if i.risk_level == RiskLevel.SAFE)
        review_count = sum(1 for i in self.items if i.risk_level == RiskLevel.REVIEW)
        risk_text    = f"{safe_count} safe"
        if review_count:
            risk_text += f"  ·  {review_count} review"
        h.addWidget(_stat("Risk", risk_text, "#fbbf24" if review_count else "#4ade80"))

        h.addStretch()
        return w

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_dry_run(self):
        self.requested_dry_run = True
        self.accept()

    def _on_backup_now(self):
        from app.services.backup_service import backup_warnings
        # Group warnings by item
        for item in self.items:
            item_warnings = [w for w in self._all_warnings
                             if w.file_path.startswith(item.path)]
            if not item_warnings:
                continue
            ok, result = backup_warnings(item_warnings, item.name, item.path)
            if ok:
                self.backup_performed = True
                self._backup_btn.setText("✓  Backed up")
                self._backup_btn.setEnabled(False)
                self._backup_btn.setStyleSheet("color: #4ade80;")
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Backup failed", result)
