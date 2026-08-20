"""
welcome_dialog.py

First-run onboarding, privacy disclosure, and terms acceptance modal for DevCache Guardian.
Shown once on initial startup until accepted by the user.
"""
from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
)
import qtawesome as qta


class WelcomeDialog(QDialog):
    """Modal dialog presenting the initial safety philosophy, offline guarantee,
    and GPLv3 terms of use on first application startup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to DevCache Guardian")
        self.setFixedSize(580, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(18)

        # ── Header ──────────────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon("fa5s.shield-alt", color="#e06c43").pixmap(38, 38))
        header_layout.addWidget(icon_label)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        title_label = QLabel("Welcome to DevCache Guardian")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_vbox.addWidget(title_label)

        sub_label = QLabel("Developer Storage Intelligence & Safety Platform")
        sub_label.setStyleSheet("color: #a0aec0; font-size: 11px;")
        title_vbox.addWidget(sub_label)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # ── Separator ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #2d3748;")
        layout.addWidget(sep)

        # ── Guarantees Card Container ────────────────────────────────────────
        cards_widget = QWidget()
        cards_vbox = QVBoxLayout(cards_widget)
        cards_vbox.setContentsMargins(0, 0, 0, 0)
        cards_vbox.setSpacing(12)

        # 1. Privacy guarantee
        self._add_feature_card(
            cards_vbox,
            icon="fa5s.lock",
            icon_color="#48bb78",
            title="100% Offline & Private",
            desc="Zero telemetry, zero analytics, and zero external network calls. All scan snapshots, databases, and logs stay strictly on your machine."
        )

        # 2. Safety Rule
        self._add_feature_card(
            cards_vbox,
            icon="fa5s.terminal",
            icon_color="#63b3ed",
            title="Explain Before Deleting",
            desc="No automated background deletions. Every cleanup requires your explicit confirmation and shows the exact command before anything runs."
        )

        # 3. Two-Layer Guardrail
        self._add_feature_card(
            cards_vbox,
            icon="fa5s.layer-group",
            icon_color="#ed8936",
            title="Two-Layer Safety Guardrails",
            desc="Virtual environments (.venv, Conda) are protected (info-only). Config files (like gradle.properties or config.json) inside caches are automatically preserved."
        )

        layout.addWidget(cards_widget)

        # ── License & Disclaimer Box ─────────────────────────────────────────
        disclaimer_box = QFrame()
        disclaimer_box.setStyleSheet(
            "background-color: #1a202c; border: 1px solid #2d3748; border-radius: 6px; padding: 10px;"
        )
        disc_layout = QVBoxLayout(disclaimer_box)
        disc_layout.setContentsMargins(10, 8, 10, 8)
        disc_layout.setSpacing(4)

        disc_title = QLabel("License & Terms of Use (GPLv3)")
        disc_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #cbd5e0;")
        disc_layout.addWidget(disc_title)

        disc_text = QLabel(
            "DevCache Guardian is open source under the GPLv3 license. It is provided "
            "\"as is\" without warranty of any kind. You maintain full control over all file deletions."
        )
        disc_text.setStyleSheet("color: #a0aec0; font-size: 10px;")
        disc_text.setWordWrap(True)
        disc_layout.addWidget(disc_text)

        layout.addWidget(disclaimer_box)
        layout.addStretch()

        # ── Action Buttons ───────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_decline = QPushButton("Decline & Exit")
        self.btn_decline.setStyleSheet(
            "QPushButton { background-color: #2d3748; color: #e2e8f0; border: none; border-radius: 5px; padding: 8px 18px; font-size: 12px; }"
            "QPushButton:hover { background-color: #4a5568; }"
        )
        self.btn_decline.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_decline)

        btn_layout.addStretch()

        self.btn_agree = QPushButton("Agree & Continue")
        self.btn_agree.setStyleSheet(
            "QPushButton { background-color: #e06c43; color: #ffffff; border: none; border-radius: 5px; padding: 8px 22px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: #f07d54; }"
        )
        self.btn_agree.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_agree)

        layout.addLayout(btn_layout)

    def _add_feature_card(self, parent_layout: QVBoxLayout, icon: str, icon_color: str, title: str, desc: str):
        card = QFrame()
        card.setStyleSheet(
            "background-color: #1a202c; border: 1px solid #2d3748; border-radius: 6px;"
        )
        h_layout = QHBoxLayout(card)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(12)

        ic_lbl = QLabel()
        ic_lbl.setPixmap(qta.icon(icon, color=icon_color).pixmap(22, 22))
        h_layout.addWidget(ic_lbl, 0, Qt.AlignTop)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-weight: bold; font-size: 11px; color: #f7fafc;")
        text_vbox.addWidget(t_lbl)

        d_lbl = QLabel(desc)
        d_lbl.setStyleSheet("color: #a0aec0; font-size: 10px;")
        d_lbl.setWordWrap(True)
        text_vbox.addWidget(d_lbl)

        h_layout.addLayout(text_vbox)
        parent_layout.addWidget(card)


class LegalViewerDialog(QDialog):
    """Dialog for viewing the full text of the Privacy Policy or GPLv3 License
    directly inside the application."""

    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(650, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        title_lbl = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        layout.addWidget(title_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #2d3748; background-color: #13171f; border-radius: 4px; }")

        text_label = QLabel(content)
        text_label.setStyleSheet("color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 12px;")
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        scroll.setWidget(text_label)

        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(
            "QPushButton { background-color: #2d3748; color: #ffffff; border-radius: 4px; padding: 6px 18px; }"
            "QPushButton:hover { background-color: #4a5568; }"
        )
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
