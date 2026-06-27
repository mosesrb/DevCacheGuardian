STYLESHEET = """
/* ── Global ─────────────────────────────────────────────────── */
* {
    font-family: "Segoe UI", "SF Pro Text", "Inter", sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget#centralWidget {
    background: #111214;
}

/* ── Sidebar ─────────────────────────────────────────────────── */
QWidget#sidebar {
    background: #0d0e10;
    border-right: 1px solid #1e2025;
}
QLabel#appTitle {
    font-size: 11px;
    font-weight: 600;
    color: #4a4f5a;
    letter-spacing: 1px;
    padding: 18px 16px 6px;
}
QPushButton#navBtn {
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-radius: 0px;
    text-align: left;
    padding: 9px 16px;
    color: #6b7280;
    font-size: 13px;
}
QPushButton#navBtn:hover {
    background: #16181c;
    color: #c9cdd6;
}
QPushButton#navBtn[active="true"] {
    border-left: 2px solid #3b82f6;
    background: #13151a;
    color: #e2e8f0;
    font-weight: 600;
}
QLabel#navSection {
    font-size: 10px;
    font-weight: 600;
    color: #374151;
    letter-spacing: 0.8px;
    padding: 14px 16px 4px;
}

/* ── Top bar ─────────────────────────────────────────────────── */
QWidget#topbar {
    background: #111214;
    border-bottom: 1px solid #1e2025;
}
QLabel#topbarTitle {
    font-size: 15px;
    font-weight: 600;
    color: #e2e8f0;
}

/* ── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background: #1a1d22;
    color: #c9cdd6;
    border: 1px solid #2a2d35;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 12px;
}
QPushButton:hover {
    background: #22262e;
    border-color: #3a3f4a;
    color: #e2e8f0;
}
QPushButton:pressed {
    background: #181b20;
}
QPushButton#btnPrimary {
    background: #1d4ed8;
    color: #ffffff;
    border: 1px solid #2563eb;
    font-weight: 600;
}
QPushButton#btnPrimary:hover {
    background: #2563eb;
    border-color: #3b82f6;
}
QPushButton#btnPrimary:pressed {
    background: #1e40af;
}
QPushButton#btnDanger {
    background: #7f1d1d;
    color: #fca5a5;
    border: 1px solid #991b1b;
}
QPushButton#btnDanger:hover {
    background: #991b1b;
}
QPushButton#btnWarning {
    background: #78350f;
    color: #fcd34d;
    border: 1px solid #92400e;
}
QPushButton#btnWarning:hover {
    background: #92400e;
}

/* ── Metric cards ─────────────────────────────────────────────── */
QWidget#metricCard {
    background: #16181c;
    border: 1px solid #1e2025;
    border-radius: 8px;
}
QLabel#metricLabel {
    font-size: 10px;
    color: #4b5563;
    letter-spacing: 0.5px;
}
QLabel#metricValue {
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}
QLabel#metricSub {
    font-size: 11px;
    color: #374151;
}

/* ── Cache table ─────────────────────────────────────────────── */
QTableWidget {
    background: #111214;
    gridline-color: #1a1d22;
    border: 1px solid #1e2025;
    border-radius: 8px;
    color: #c9cdd6;
    selection-background-color: #1a2a4a;
    selection-color: #e2e8f0;
    alternate-background-color: #13151a;
}
QTableWidget::item {
    padding: 6px 10px;
    border: none;
}
QTableWidget::item:hover {
    background: #16181c;
}
QHeaderView::section {
    background: #0d0e10;
    color: #4b5563;
    border: none;
    border-bottom: 1px solid #1e2025;
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QHeaderView::section:hover {
    background: #13151a;
    color: #6b7280;
}

/* ── Scroll bars ─────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2d35;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #3a3f4a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    height: 6px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    background: #2a2d35;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ── Detail panel ─────────────────────────────────────────────── */
QWidget#detailPanel {
    background: #13151a;
    border: 1px solid #1e2025;
    border-radius: 8px;
}
QLabel#detailTitle {
    font-size: 14px;
    font-weight: 600;
    color: #e2e8f0;
}
QLabel#detailFieldLabel {
    font-size: 10px;
    color: #374151;
    letter-spacing: 0.5px;
}
QLabel#detailFieldValue {
    font-size: 13px;
    color: #c9cdd6;
}
QLabel#detailLongDesc {
    font-size: 13px;
    color: #6b7280;
    line-height: 1.6;
}
QLabel#cmdLabel {
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    color: #93c5fd;
    background: #0d1117;
    border: 1px solid #1e2025;
    border-radius: 6px;
    padding: 8px 12px;
}

/* ── Risk badges ─────────────────────────────────────────────── */
QLabel#badgeSafe {
    background: #052e16;
    color: #4ade80;
    border: 1px solid #14532d;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#badgeReview {
    background: #1c1917;
    color: #fbbf24;
    border: 1px solid #451a03;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#badgeDanger {
    background: #1c0404;
    color: #f87171;
    border: 1px solid #450a0a;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* ── Progress bar ─────────────────────────────────────────────── */
QProgressBar {
    background: #1a1d22;
    border: 1px solid #1e2025;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: #2563eb;
    border-radius: 4px;
}

/* ── Dialog / overlay ─────────────────────────────────────────── */
QDialog {
    background: #111214;
    border: 1px solid #2a2d35;
    border-radius: 12px;
}
QDialog QLabel {
    color: #c9cdd6;
}

/* ── Search / input ─────────────────────────────────────────────── */
QLineEdit {
    background: #16181c;
    border: 1px solid #2a2d35;
    border-radius: 6px;
    color: #c9cdd6;
    padding: 6px 10px;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #2563eb;
    background: #13151a;
}

/* ── Combo/Select ─────────────────────────────────────────────── */
QComboBox {
    background: #16181c;
    border: 1px solid #2a2d35;
    border-radius: 6px;
    color: #c9cdd6;
    padding: 6px 10px;
    font-size: 12px;
}
QComboBox::drop-down { border: none; }
QComboBox:hover { border-color: #3a3f4a; }
QComboBox QAbstractItemView {
    background: #16181c;
    border: 1px solid #2a2d35;
    color: #c9cdd6;
    selection-background-color: #1d4ed8;
}

/* ── Separator ─────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    border: none;
    background: #1e2025;
    max-height: 1px;
}

/* ── Checkbox ─────────────────────────────────────────────── */
QCheckBox {
    color: #9ca3af;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #2a2d35;
    border-radius: 4px;
    background: #16181c;
}
QCheckBox::indicator:checked {
    background: #1d4ed8;
    border-color: #2563eb;
}
QCheckBox:hover { color: #c9cdd6; }

/* ── Tooltip ─────────────────────────────────────────────── */
QToolTip {
    background: #1a1d22;
    color: #c9cdd6;
    border: 1px solid #2a2d35;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
"""
