"""
ScheduledPoliciesWidget — UI for configuring cleanup schedule policies.

Each scanned cache can be assigned:
  Weekly   — proposed for cleanup every 7 days
  Monthly  — proposed for cleanup every 30 days
  Never    — excluded from scheduled runs (default)

When a policy is due, the main window shows a confirmation dialog before
any actual cleanup runs (with dry-run option). Policies never auto-clean.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from app.models import CacheItem, RiskLevel
from app.database.policies import (
    get_all_policies, upsert_policy, delete_policy, get_due_policies
)


_FREQ_OPTIONS = ["never", "weekly", "monthly"]
_FREQ_LABELS  = {"never": "Never", "weekly": "Weekly", "monthly": "Monthly"}
_FREQ_COLORS  = {"never": "#374151", "weekly": "#3b82f6", "monthly": "#a78bfa"}


class ScheduledPoliciesWidget(QWidget):
    """
    Shown as a section inside SettingsWidget.
    Also exposed as a standalone widget for the Policies tab if needed.
    """
    # Emitted when any policy changes so main window can react
    policies_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[CacheItem] = []
        self._build()

    def _build(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        # Description
        desc = QLabel(
            "Set a cleanup schedule for individual caches. "
            "Scheduled items are <b>proposed</b> for cleanup — "
            "you will always see a confirmation dialog before anything is deleted."
        )
        desc.setStyleSheet("color:#6b7280; font-size:12px;")
        desc.setWordWrap(True)
        lyt.addWidget(desc)

        # Due-now banner (hidden until check)
        self._due_banner = QLabel("")
        self._due_banner.setStyleSheet(
            "color:#fbbf24; background:#1c0a00; border:1px solid #451a03;"
            "border-radius:6px; padding:8px 12px; font-size:12px;"
        )
        self._due_banner.setWordWrap(True)
        self._due_banner.hide()
        lyt.addWidget(self._due_banner)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Cache", "Ecosystem", "Schedule", "Actions"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); hh.resizeSection(1, 110)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); hh.resizeSection(2, 110)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed); hh.resizeSection(3, 90)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        lyt.addWidget(self._table)

        # Bottom hint
        hint = QLabel("ℹ  Dangerous items (virtual environments, AI models) cannot be scheduled.")
        hint.setStyleSheet("color:#374151; font-size:11px;")
        lyt.addWidget(hint)

    # ── public API ────────────────────────────────────────────────────────────

    def update_items(self, items: List[CacheItem]):
        """Populate the table with scanned cache items."""
        self._items = [i for i in items if i.risk_level != RiskLevel.DANGER]
        self._rebuild_table()
        self._check_due()

    def refresh_from_db(self):
        """Reload table from DB policies (called on settings open)."""
        self._rebuild_table()
        self._check_due()

    # ── internal ──────────────────────────────────────────────────────────────

    def _rebuild_table(self):
        existing = {p["cache_id"]: p for p in get_all_policies()}
        items    = self._items

        # If no scan items yet, show DB policies only
        if not items:
            for policy in existing.values():
                self._add_row_from_policy(policy)
            return

        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(0)

        for item in sorted(items, key=lambda x: x.name.lower()):
            row  = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setRowHeight(row, 42)

            policy = existing.get(item.id, {})
            freq   = policy.get("frequency", "never")

            # Col 0 — name
            name_w = QWidget()
            nv     = QVBoxLayout(name_w)
            nv.setContentsMargins(10, 4, 4, 4); nv.setSpacing(1)
            name_lbl = QLabel(item.name)
            name_lbl.setStyleSheet("color:#e2e8f0; font-size:13px; font-weight:500;")
            desc_lbl = QLabel(item.description[:60] + ("…" if len(item.description)>60 else ""))
            desc_lbl.setStyleSheet("color:#374151; font-size:11px;")
            nv.addWidget(name_lbl); nv.addWidget(desc_lbl)
            self._table.setCellWidget(row, 0, name_w)

            # Col 1 — ecosystem
            from app.ui.cache_table_widget import ECO_COLORS
            eco_lbl = QLabel(item.ecosystem)
            eco_lbl.setStyleSheet(
                f"color:{ECO_COLORS.get(item.ecosystem,'#6b7280')}; font-size:12px; padding-left:8px;"
            )
            self._table.setCellWidget(row, 1, eco_lbl)

            # Col 2 — frequency picker
            combo = QComboBox()
            combo.addItems([_FREQ_LABELS[f] for f in _FREQ_OPTIONS])
            combo.setCurrentText(_FREQ_LABELS.get(freq, "Never"))
            combo.setStyleSheet(
                "QComboBox { background:#16181c; border:1px solid #2a2d35; "
                "color:#c9cdd6; border-radius:4px; padding:4px 8px; font-size:12px; }"
                "QComboBox::drop-down { border:none; }"
                "QComboBox QAbstractItemView { background:#16181c; border:1px solid #2a2d35; color:#c9cdd6; }"
            )
            combo.currentTextChanged.connect(
                lambda text, cid=item.id, cname=item.name: self._on_freq_changed(cid, cname, text)
            )
            self._table.setCellWidget(row, 2, combo)

            # Col 3 — clear button
            clear_btn = QPushButton("Clear")
            clear_btn.setStyleSheet(
                "font-size:11px; color:#6b7280; background:#1a1d22;"
                "border:1px solid #2a2d35; border-radius:4px; padding:4px 8px;"
            )
            clear_btn.clicked.connect(
                lambda _, cid=item.id, combo=combo: self._clear_policy(cid, combo)
            )
            self._table.setCellWidget(row, 3, clear_btn)

            # Hidden data
            hidden = QTableWidgetItem()
            hidden.setData(Qt.ItemDataRole.UserRole, item.id)
            self._table.setItem(row, 0, hidden)

        self._table.setUpdatesEnabled(True)

    def _add_row_from_policy(self, policy: dict):
        """Add a row for a DB policy when no scan items are loaded."""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 38)

        name_lbl = QLabel(policy.get("cache_name", "Unknown"))
        name_lbl.setStyleSheet("color:#e2e8f0; font-size:13px; padding-left:10px;")
        self._table.setCellWidget(row, 0, name_lbl)

        freq    = policy.get("frequency", "never")
        color   = _FREQ_COLORS.get(freq, "#374151")
        freq_lbl = QLabel(_FREQ_LABELS.get(freq, freq.capitalize()))
        freq_lbl.setStyleSheet(f"color:{color}; font-size:12px; font-weight:500; padding-left:8px;")
        self._table.setCellWidget(row, 2, freq_lbl)

    def _on_freq_changed(self, cache_id: str, cache_name: str, label: str):
        freq = next((k for k, v in _FREQ_LABELS.items() if v == label), "never")
        if freq == "never":
            delete_policy(cache_id)
        else:
            upsert_policy(cache_id, cache_name, freq)
        self.policies_changed.emit()

    def _clear_policy(self, cache_id: str, combo: QComboBox):
        delete_policy(cache_id)
        combo.setCurrentText("Never")
        self.policies_changed.emit()

    def _check_due(self):
        due = get_due_policies()
        if due:
            names = ", ".join(p["cache_name"] for p in due[:3])
            extra = f" and {len(due)-3} more" if len(due) > 3 else ""
            self._due_banner.setText(
                f"⏰  {len(due)} scheduled cleanup(s) are due: {names}{extra}. "
                "Go to Cache Explorer and use 'Clean safe items' to run them."
            )
            self._due_banner.show()
        else:
            self._due_banner.hide()
