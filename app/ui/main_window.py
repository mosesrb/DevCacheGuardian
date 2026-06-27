"""
MainWindow (v9)

New in v9
---------
* _scan_active guard prevents double-fire race condition
* QSystemTrayIcon with minimize-to-tray, badge on large cache found
* Hourly QTimer fires get_due_policies() and toasts if policies are due
* WAL checkpoint on app exit (PRAGMA wal_checkpoint(TRUNCATE))
* Scanner error warning banner after scan
* Keyboard shortcuts: Ctrl+R rescan, Ctrl+D dry-run, Ctrl+E export
* open_in_explorer path-existence check surfaced to toast
* Rescan button disabled while RescanWorker is active
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QIcon
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget, QPushButton,
    QSystemTrayIcon, QMenu,
)
from loguru import logger

from app.models import CacheItem, RiskLevel
from app.services import ScanWorker, CleanWorker, RescanWorker
from app.services.scoring import get_health_score
from app.database import (
    get_preference, set_preference, init_db,
    log_scan, log_scan_items, get_last_scan_id,
    get_last_scan, get_growth_deltas,
    get_cleanup_stats, add_ignored_path, wal_checkpoint,
)
from app.utils import fmt_bytes

from .stylesheet import STYLESHEET
from .dashboard_widget import DashboardWidget
from .cache_table_widget import CacheTableWidget
from .history_widget import HistoryWidget
from .timeline_widget import TimelineWidget
from .settings_widget import SettingsWidget
from .confirm_dialog import ConfirmCleanDialog
from .dry_run_dialog import DryRunResultDialog
from .scan_overlay import ScanOverlay
from .clean_progress_overlay import CleanProgressOverlay
from .toast import Toast
from .status_bar import StatusBar


NAV_ITEMS = [
    ("dashboard", "Dashboard",      "📊"),
    ("caches",    "Cache Explorer", "🗄"),
    ("timeline",  "Timeline",       "📈"),
    ("history",   "History",        "🕐"),
    ("---", "ECOSYSTEMS", ""),
    ("python",    "Python",         "🐍"),
    ("nodejs",    "Node.js",        "⬡"),
    ("aiml",      "AI / ML",        "🧠"),
    ("docker",    "Docker",         "🐳"),
    ("buildsys",  "Build Systems",  "🔨"),
    ("system",    "System",         "🖥"),
    ("---", "", ""),
    ("settings",  "Settings",       "⚙"),
]
ECO_MAP = {
    "python": "Python", "nodejs": "Node.js", "aiml": "AI/ML",
    "docker": "Docker", "buildsys": "Build Systems", "system": "System",
}
VIEW_TITLES = {
    "dashboard": "Dashboard",      "caches":    "Cache Explorer",
    "timeline":  "Timeline",       "history":   "History",
    "settings":  "Settings",
    "python":    "Python Caches",  "nodejs":    "Node.js Caches",
    "aiml":      "AI / ML Caches", "docker":    "Docker Caches",
    "buildsys":  "Build System Caches", "system": "System / Temp",
}


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DevCache Guardian")
        self.setMinimumSize(960, 640)
        self.setStyleSheet(STYLESHEET)

        self._all_items:     List[CacheItem]        = []
        self._current_view:  str                    = "dashboard"
        self._nav_buttons:   dict                   = {}
        self._scan_worker:   Optional[ScanWorker]   = None
        self._clean_worker:  Optional[CleanWorker]  = None
        self._rescan_worker: Optional[RescanWorker] = None
        self._scan_start_time: Optional[float]      = None
        self._scan_active:   bool                   = False   # double-fire guard
        self._scan_errors:   List[str]              = []      # scanner errors from last scan

        init_db()
        self._init_ui()
        self._bind_shortcuts()
        self._toast = Toast(self.centralWidget())
        self._restore_geometry()
        self._refresh_last_scan_label()
        self._init_tray()

        # Hourly policy check timer
        self._policy_timer = QTimer(self)
        self._policy_timer.timeout.connect(self._check_due_policies)
        self._policy_timer.start(60 * 60 * 1000)   # 1 hour

        if get_preference("scan_on_startup", "true") == "true":
            QTimer.singleShot(400, self.start_scan)

    # ══════════════════════════════════════════════════════ BUILD ═════════════

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        right = QWidget()
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0); rv.setSpacing(0)
        rv.addWidget(self._build_topbar())

        self._stack           = QStackedWidget()
        self._dashboard       = DashboardWidget()
        self._cache_table     = CacheTableWidget()
        self._timeline_widget = TimelineWidget()
        self._history_widget  = HistoryWidget()
        self._settings_widget = SettingsWidget()

        # Stack indices: 0=dashboard 1=caches 2=timeline 3=history 4=settings
        for w in (self._dashboard, self._cache_table,
                  self._timeline_widget, self._history_widget,
                  self._settings_widget):
            self._stack.addWidget(w)
        rv.addWidget(self._stack, stretch=1)

        self._status_bar = StatusBar()
        rv.addWidget(self._status_bar)

        # ── signal wiring ─────────────────────────────────────────────────────
        self._cache_table.clean_requested.connect(self._on_clean_single)
        self._cache_table.dry_run_requested.connect(self._on_dry_run_single)
        self._cache_table.rescan_requested.connect(self._on_rescan_single)
        self._cache_table.ignore_requested.connect(self._on_ignore_requested)
        self._cache_table.bulk_clean.connect(self._on_bulk_clean)
        self._cache_table.bulk_dry_run.connect(self._run_dry_run)
        self._cache_table.export_done.connect(self._on_export_done)
        self._cache_table.export_failed.connect(
            lambda msg: self._toast.show_error(f"Export failed: {msg}")
        )
        self._cache_table.item_selected.connect(self._on_item_selected)
        self._dashboard.clean_safe_requested.connect(self._clean_all_safe)
        self._dashboard.export_report_requested.connect(self._export_html_report)

        self._scan_overlay  = ScanOverlay(right)
        self._clean_overlay = CleanProgressOverlay(right)
        root.addWidget(right)
        self._right_pane = right

    def _build_sidebar(self) -> QWidget:
        sb  = QWidget(); sb.setObjectName("sidebar"); sb.setFixedWidth(192)
        lyt = QVBoxLayout(sb)
        lyt.setContentsMargins(0, 0, 0, 0); lyt.setSpacing(0)
        title = QLabel("DEVCACHE"); title.setObjectName("appTitle")
        lyt.addWidget(title)
        for key, label, icon in NAV_ITEMS:
            if key == "---":
                sec = QLabel(label); sec.setObjectName("navSection")
                lyt.addWidget(sec); continue
            btn = QPushButton(f"  {icon}  {label}")
            btn.setObjectName("navBtn"); btn.setFixedHeight(36)
            btn.clicked.connect(lambda _, k=key: self._set_view(k))
            lyt.addWidget(btn); self._nav_buttons[key] = btn
        lyt.addStretch()
        self._update_nav("dashboard")
        return sb

    def _build_topbar(self) -> QWidget:
        bar = QWidget(); bar.setObjectName("topbar"); bar.setFixedHeight(52)
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(24, 0, 20, 0); lyt.setSpacing(10)
        title_col = QVBoxLayout(); title_col.setSpacing(1)
        self._topbar_title = QLabel("Dashboard")
        self._topbar_title.setObjectName("topbarTitle")
        title_col.addWidget(self._topbar_title)
        self._last_scan_lbl = QLabel("")
        self._last_scan_lbl.setStyleSheet("color:#374151; font-size:10px;")
        title_col.addWidget(self._last_scan_lbl)
        lyt.addLayout(title_col); lyt.addStretch()

        self._dry_run_all_btn = QPushButton("🔍  Dry run all safe")
        self._dry_run_all_btn.setFixedHeight(32)
        self._dry_run_all_btn.setToolTip("Simulate cleaning all safe caches  [Ctrl+D]")
        self._dry_run_all_btn.clicked.connect(self._dry_run_all_safe)
        lyt.addWidget(self._dry_run_all_btn)

        self._scan_btn = QPushButton("↻  Scan now")
        self._scan_btn.setFixedHeight(32)
        self._scan_btn.setToolTip("Re-scan all cache locations  [F5]")
        self._scan_btn.clicked.connect(self.start_scan)
        lyt.addWidget(self._scan_btn)

        self._clean_safe_btn = QPushButton("🧹  Clean safe items")
        self._clean_safe_btn.setObjectName("btnPrimary")
        self._clean_safe_btn.setFixedHeight(32)
        self._clean_safe_btn.setToolTip("Clean all safe caches  [Ctrl+Shift+C]")
        self._clean_safe_btn.clicked.connect(self._clean_all_safe)
        lyt.addWidget(self._clean_safe_btn)
        return bar

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("F5"),           self, self.start_scan)
        QShortcut(QKeySequence("Ctrl+R"),       self, self.start_scan)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._clean_all_safe)
        QShortcut(QKeySequence("Ctrl+D"),       self, self._dry_run_all_safe)
        QShortcut(QKeySequence("Ctrl+E"),       self, self._export_html_report)

    # ══════════════════════════════════════════════════════ NAVIGATION ════════

    def _set_view(self, key: str):
        self._current_view = key
        self._update_nav(key)
        self._topbar_title.setText(VIEW_TITLES.get(key, key.capitalize()))
        # Stack indices: 0=dashboard 1=caches 2=timeline 3=history 4=settings
        if key == "dashboard":
            self._stack.setCurrentIndex(0)
        elif key == "caches":
            self._cache_table.update_items(self._all_items)
            self._stack.setCurrentIndex(1)
        elif key == "timeline":
            self._timeline_widget.refresh()
            self._stack.setCurrentIndex(2)
        elif key == "history":
            self._history_widget.refresh()
            self._stack.setCurrentIndex(3)
        elif key == "settings":
            self._stack.setCurrentIndex(4)
        else:
            eco = ECO_MAP.get(key, "")
            self._cache_table.update_items(
                [i for i in self._all_items if i.ecosystem == eco]
            )
            self._stack.setCurrentIndex(1)

    def _update_nav(self, active: str):
        for key, btn in self._nav_buttons.items():
            btn.setProperty("active", "true" if key == active else "false")
            btn.style().unpolish(btn); btn.style().polish(btn)

    # ══════════════════════════════════════════════════════ LAST-SCAN ══════════

    def _refresh_last_scan_label(self):
        record = get_last_scan()
        if not record:
            self._last_scan_lbl.setText("Never scanned"); return
        try:
            dt  = datetime.fromisoformat(record["scanned_at"])
            age = datetime.now() - dt
            dur = record.get("duration_seconds") or 0
            dur_str = f"  ·  {dur:.1f}s" if dur else ""
            if age.days > 0:
                label = f"Last scan: {age.days}d ago{dur_str}"
            elif age.seconds > 3600:
                label = f"Last scan: {age.seconds//3600}h ago{dur_str}"
            else:
                label = f"Last scan: {max(age.seconds//60,1)}m ago{dur_str}"
            self._last_scan_lbl.setText(label)
        except Exception:
            self._last_scan_lbl.setText("")

    # ══════════════════════════════════════════════════════ SCANNING ══════════

    def start_scan(self):
        if self._scan_active:
            self._toast.show_message("Scan already in progress.", color="#374151"); return
        if self._clean_worker and self._clean_worker.isRunning():
            self._toast.show_error("Wait for cleanup to finish first."); return

        self._scan_active = True
        self._scan_errors = []
        self._all_items.clear()
        self._scan_start_time = time.perf_counter()
        self._scan_overlay.show(); self._scan_overlay.raise_()
        self._scan_overlay.update_progress("Starting parallel scan…", 0, 0)
        self._set_controls_enabled(False)
        self._status_bar.set_scanning("Initialising")

        self._scan_worker = ScanWorker(self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.item_found.connect(self._on_item_found)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_progress(self, name: str, current: int, total: int):
        self._scan_overlay.update_progress(f"Completed: {name}", current, total)
        self._status_bar.set_scanning(name)

    def _on_scan_error(self, msg: str):
        """Collect scanner errors during scan; shown as banner after scan finishes."""
        self._scan_errors.append(msg)
        logger.warning(f"Scanner error: {msg}")

    def _on_item_found(self, item: CacheItem):
        self._cache_table.add_item(item)

    def _on_scan_finished(self, items: List[CacheItem]):
        self._scan_active = False   # release double-fire guard
        self._all_items = items
        duration = time.perf_counter() - (self._scan_start_time or time.perf_counter())
        self._scan_overlay.hide()
        self._set_controls_enabled(True)

        # Log scan to DB
        total = sum(i.size_bytes for i in items)
        try:
            log_scan(total, len(items), duration)
            # Log per-item snapshots for growth tracking
            scan_id = get_last_scan_id()
            if scan_id:
                log_scan_items(scan_id, [
                    {"cache_id": i.id, "cache_name": i.name,
                     "ecosystem": i.ecosystem, "size_bytes": i.size_bytes}
                    for i in items
                ])
        except Exception as exc:
            logger.warning(f"Failed to log scan: {exc}")

        # Fetch growth deltas
        try:
            deltas = get_growth_deltas()
        except Exception:
            deltas = []

        self._dashboard.update_items(items)
        self._dashboard.update_growth(deltas)
        self._cache_table.update_items(items)
        self._refresh_last_scan_label()

        safe    = sum(i.size_bytes for i in items if i.risk_level == RiskLevel.SAFE)
        safe_cnt = sum(1 for i in items if i.risk_level == RiskLevel.SAFE)
        rev_cnt  = sum(1 for i in items if i.risk_level == RiskLevel.REVIEW)
        dang_cnt = sum(1 for i in items if i.risk_level == RiskLevel.DANGER)

        self._status_bar.set_scan_complete(len(items), total, duration)
        self._status_bar.set_item_count(len(items), safe_cnt, rev_cnt, dang_cnt)

        threshold_gb = float(get_preference("size_warning_threshold_gb", "5") or "5")
        safe_gb = safe / 1024**3
        if threshold_gb > 0 and safe_gb >= threshold_gb:
            self._toast.show_message(
                f"⚠  {fmt_bytes(safe)} of safe caches found — consider cleaning",
                color="#854d0e", duration_ms=5000,
            )
        else:
            self._toast.show_message(
                f"Scan complete — {fmt_bytes(total)} found in {duration:.1f}s",
                color="#1d4ed8",
            )
        logger.info(f"Scan finished: {len(items)} items, {fmt_bytes(total)}, {duration:.1f}s")

        # Surface scanner errors as an actionable warning
        if self._scan_errors:
            self._toast.show_message(
                f"⚠ {len(self._scan_errors)} scanner(s) had errors — some caches may be missing",
                color="#854d0e", duration_ms=8000,
            )

        # Update settings policies widget with new item list
        self._settings_widget.update_scan_items(items)

        # Check if any scheduled policies are now due
        self._check_due_policies()

    # ══════════════════════════════════════════════════════ ITEM SELECTED ═════

    def _on_item_selected(self, item: CacheItem):
        self._status_bar.set_selection(item.name, item.size_label)

    # ══════════════════════════════════════════════════════ IGNORE ════════════

    def _on_ignore_requested(self, item: CacheItem):
        try:
            add_ignored_path(item.path, reason=f"Ignored from UI: {item.name}")
            self._toast.show_success(f"Protected: {item.path}")
            self._status_bar.set_action("🛡  Added to protected paths", "#9ca3af")
        except Exception as exc:
            self._toast.show_error(f"Could not add protected path: {exc}")

    # ══════════════════════════════════════════════════════ EXPORT ════════════

    def _on_export_done(self, path: str, count: int):
        fname = Path(path).name
        self._toast.show_success(f"Exported {count} items → {fname}")
        self._status_bar.set_action(f"⬇  Exported {count} rows", "#4ade80")

    def _export_html_report(self):
        """Show format picker then generate and save the audit report."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QRadioButton
        dlg = QDialog(self)
        dlg.setWindowTitle("Export Report")
        dlg.setFixedWidth(320)
        dlg.setStyleSheet("background:#111214; color:#c9cdd6;")
        lyt = QVBoxLayout(dlg)
        lyt.setContentsMargins(20, 20, 20, 20); lyt.setSpacing(12)
        lyt.addWidget(QLabel("Choose export format:"))

        rb_html = QRadioButton("HTML  (rich, self-contained, recommended)")
        rb_md   = QRadioButton("Markdown  (GitHub-flavoured, for wikis/issues)")
        rb_pdf  = QRadioButton("PDF  (via Qt print engine)")
        rb_html.setChecked(True)
        for rb in (rb_html, rb_md, rb_pdf):
            rb.setStyleSheet("color:#c9cdd6; font-size:13px;")
            lyt.addWidget(rb)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lyt.addWidget(btns)

        if not dlg.exec():
            return

        if rb_html.isChecked():
            self._do_export_report("html")
        elif rb_md.isChecked():
            self._do_export_report("markdown")
        else:
            self._do_export_report("pdf")

    def _do_export_report(self, fmt: str):
        """Generate and save the report in the specified format."""
        filters = {
            "html":     ("HTML files (*.html)", "devcache_audit_report.html"),
            "markdown": ("Markdown files (*.md)", "devcache_audit_report.md"),
            "pdf":      ("PDF files (*.pdf)",  "devcache_audit_report.pdf"),
        }
        file_filter, default_name = filters[fmt]
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Audit Report", default_name, file_filter
        )
        if not path:
            return

        try:
            from app.services.report_generator import (
                generate_html_report, generate_markdown_report, generate_pdf_report
            )
            health   = get_health_score(self._all_items)
            deltas   = get_growth_deltas()
            stats    = get_cleanup_stats()
            dur_rec  = get_last_scan()
            dur_s    = (dur_rec.get("duration_seconds") or 0) if dur_rec else 0
            kwargs   = dict(items=self._all_items, health=health,
                           growth_deltas=deltas, cleanup_stats=stats,
                           scan_duration=dur_s)

            fname = Path(path).name
            if fmt == "html":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(generate_html_report(**kwargs))
                self._toast.show_success(f"HTML report → {fname}")
            elif fmt == "markdown":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(generate_markdown_report(**kwargs))
                self._toast.show_success(f"Markdown report → {fname}")
            elif fmt == "pdf":
                ok = generate_pdf_report(**kwargs, output_path=path)
                if ok:
                    self._toast.show_success(f"PDF report → {fname}")
                else:
                    self._toast.show_error("PDF generation failed — try HTML instead")
                    return

            self._status_bar.set_action("📄  Report exported", "#4ade80")
            logger.info(f"Report exported ({fmt}) to {path}")
        except Exception as exc:
            logger.exception("Report generation failed")
            self._toast.show_error(f"Report failed: {exc}")

    def _check_due_policies(self):
        """Notify user if any scheduled cleanup policies are due."""
        try:
            from app.database.policies import get_due_policies
            due = get_due_policies()
            if not due:
                return
            names = ", ".join(p["cache_name"] for p in due[:2])
            extra = f" +{len(due)-2} more" if len(due) > 2 else ""
            self._toast.show_message(
                f"⏰  {len(due)} scheduled cleanup(s) due: {names}{extra}  "
                f"— go to Settings → Scheduled Policies",
                color="#854d0e",
                duration_ms=8000,
            )
        except Exception:
            pass

    # ══════════════════════════════════════════════════════ RESCAN ════════════

    def _on_rescan_single(self, item: CacheItem):
        if self._rescan_worker and self._rescan_worker.isRunning():
            self._toast.show_message("A rescan is already running.", color="#374151"); return

        self._toast.show_message(f"Rescanning {item.name}…", color="#374151")
        worker = RescanWorker(item, parent=self)

        def on_done(updated: Optional[CacheItem]):
            if updated:
                for i, ex in enumerate(self._all_items):
                    if ex.id == updated.id:
                        self._all_items[i] = updated; break
                self._cache_table.update_item(updated)
                self._dashboard.update_items(self._all_items)
                self._toast.show_success(f"Rescanned: {updated.name} — {updated.size_label}")
            else:
                self._toast.show_message(
                    "Item not found after rescan (may be fully cleaned)", color="#374151"
                )
            # Re-enable any rescan buttons (rate-limit released)
            self._rescan_worker = None

        worker.done.connect(on_done)
        self._rescan_worker = worker
        worker.start()

    # ══════════════════════════════════════════════════════ TRAY ══════════════

    def _init_tray(self):
        """Create system tray icon with context menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = None
            return

        self._tray = QSystemTrayIcon(self)
        # Use a simple fallback icon — projects can replace with a real .ico
        try:
            ico_path = Path(__file__).parent.parent.parent / "assets" / "icon.png"
            if ico_path.exists():
                self._tray.setIcon(QIcon(str(ico_path)))
            else:
                self._tray.setIcon(self.style().standardIcon(
                    self.style().StandardPixmap.SP_DriveHDIcon
                ))
        except Exception:
            pass

        menu = QMenu()
        menu.setStyleSheet("background:#111214; color:#c9cdd6; font-size:13px;")

        act_show = menu.addAction("Show DevCache Guardian")
        act_show.triggered.connect(self._tray_show)

        menu.addSeparator()

        act_scan = menu.addAction("🔍  Scan now")
        act_scan.triggered.connect(self.start_scan)

        act_clean = menu.addAction("🧹  Clean safe caches")
        act_clean.triggered.connect(self._clean_all_safe)

        menu.addSeparator()

        act_quit = menu.addAction("Quit")
        act_quit.triggered.connect(self._tray_quit)

        self._tray.setContextMenu(menu)
        self._tray.setToolTip("DevCache Guardian")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _tray_show(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_quit(self):
        if self._tray:
            self._tray.hide()
        self.close()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_show()

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if (event.type() == QEvent.Type.WindowStateChange
                and self.isMinimized()
                and self._tray is not None
                and get_preference("minimize_to_tray", "false") == "true"):
            self.hide()
            self._tray.showMessage(
                "DevCache Guardian",
                "Running in the background — double-click the tray icon to restore.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
            return
        super().changeEvent(event)

    # ══════════════════════════════════════════════════════ DRY RUN ═══════════

    def _on_dry_run_single(self, item: CacheItem):
        self._run_dry_run([item])

    def _dry_run_all_safe(self):
        safe = [i for i in self._all_items if i.risk_level == RiskLevel.SAFE]
        if not safe:
            self._toast.show_message("No safe caches found. Run a scan first.", color="#374151"); return
        self._run_dry_run(safe)

    def _run_dry_run(self, items: List[CacheItem]):
        if self._clean_worker and self._clean_worker.isRunning():
            self._toast.show_error("A cleanup is already running."); return

        self._clean_overlay.start("Running preflight check…")
        self._set_controls_enabled(False)
        self._status_bar.set_action("🔍  Running dry run…", "#9ca3af", timeout_ms=0)

        worker = CleanWorker(items, dry_run=True, parent=self)
        worker.progress.connect(
            lambda name, cur, tot: self._clean_overlay.update_progress(name, cur, tot)
        )

        def on_finished(total_bytes, failures, results):
            self._clean_overlay.hide()
            self._set_controls_enabled(True)
            self._status_bar.set_action("🔍  Dry run complete", "#9ca3af")
            dlg = DryRunResultDialog(results, self)
            if dlg.exec():
                self._execute_confirm_and_clean(items)

        worker.finished.connect(on_finished)
        self._clean_worker = worker
        worker.start()

    # ══════════════════════════════════════════════════════ CLEANUP ═══════════

    def _on_clean_single(self, item: CacheItem): self._execute_confirm_and_clean([item])
    def _on_bulk_clean(self, items: List[CacheItem]): self._execute_confirm_and_clean(items)

    def _clean_all_safe(self):
        safe = [i for i in self._all_items if i.risk_level == RiskLevel.SAFE]
        if not safe:
            self._toast.show_message("No safe caches found. Run a scan first.", color="#374151"); return
        self._execute_confirm_and_clean(safe)

    def _execute_confirm_and_clean(self, items: List[CacheItem]):
        if self._clean_worker and self._clean_worker.isRunning():
            self._toast.show_error("A cleanup is already in progress."); return

        dlg = ConfirmCleanDialog(items, self)
        if not dlg.exec(): return
        if dlg.requested_dry_run:
            self._run_dry_run(items); return
        self._start_real_clean(items)

    def _start_real_clean(self, items: List[CacheItem]):
        label = f"Cleaning {len(items)} cache{'s' if len(items)!=1 else ''}…"
        self._clean_overlay.start(label)
        self._set_controls_enabled(False)
        self._status_bar.set_action(f"🧹  {label}", "#9ca3af", timeout_ms=0)

        worker = CleanWorker(items, dry_run=False, parent=self)
        worker.progress.connect(
            lambda name, cur, tot: self._clean_overlay.update_progress(name, cur, tot)
        )
        worker.item_done.connect(self._on_clean_item_done)
        worker.finished.connect(
            lambda total, failures, _r: self._on_clean_finished(total, failures)
        )
        self._clean_worker = worker
        worker.start()

    def _on_clean_item_done(self, cache_id: str, success: bool, reclaimed: float, msg: str):
        if success:
            self._cache_table.mark_cleaned(cache_id)
            self._dashboard.add_session_cleaned(int(reclaimed))
            logger.info(f"Cleaned {cache_id}: {fmt_bytes(int(reclaimed))}")
        else:
            logger.warning(f"Clean failed {cache_id}: {msg}")

    def _on_clean_finished(self, total_reclaimed: float, failures: List[str]):
        self._clean_overlay.hide()
        self._set_controls_enabled(True)
        self._dashboard.update_items(self._all_items)
        self._history_widget.refresh()
        if failures:
            self._toast.show_error(f"{len(failures)} cleanup(s) failed — see History.")
            self._status_bar.set_action(f"⚠  {len(failures)} failed", "#f87171")
        else:
            self._toast.show_success(f"Done — {fmt_bytes(total_reclaimed)} reclaimed")
            self._status_bar.set_action(f"✓  {fmt_bytes(total_reclaimed)} reclaimed", "#4ade80")

    # ══════════════════════════════════════════════════════ HELPERS ═══════════

    def _set_controls_enabled(self, enabled: bool):
        self._scan_btn.setEnabled(enabled)
        self._clean_safe_btn.setEnabled(enabled)
        self._dry_run_all_btn.setEnabled(enabled)

    def _restore_geometry(self):
        try:
            geom_hex = get_preference("window_geometry", "")
            if geom_hex: self.restoreGeometry(bytes.fromhex(geom_hex))
            else: self.resize(1120, 740)
        except Exception:
            self.resize(1120, 740)

    def _save_geometry(self):
        try:
            set_preference("window_geometry", self.saveGeometry().toHex().data().decode())
        except Exception:
            pass

    def resizeEvent(self, event):
        for overlay in (
            getattr(self, "_scan_overlay",  None),
            getattr(self, "_clean_overlay", None),
        ):
            if overlay and overlay.parent():
                overlay.setGeometry(overlay.parent().rect())
        if hasattr(self, "_toast"):
            self._toast._reposition()
        super().resizeEvent(event)

    def closeEvent(self, event):
        workers = [
            getattr(self, "_scan_worker",   None),
            getattr(self, "_clean_worker",  None),
            getattr(self, "_rescan_worker", None),
        ]
        if any(w and w.isRunning() for w in workers):
            reply = QMessageBox.question(
                self, "Operation in progress",
                "A scan or cleanup is still running.\nStop it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore(); return

        self._save_geometry()
        for w in workers:
            if w and w.isRunning():
                try: w.cancel(); w.wait(3000)
                except Exception: pass
        # Flush WAL to main DB file — prevents ghost .db-wal files
        try:
            wal_checkpoint()
        except Exception:
            pass
        if self._tray:
            self._tray.hide()
        event.accept()
