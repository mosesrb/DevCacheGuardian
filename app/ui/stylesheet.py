"""
stylesheet.py

Builds the application QSS from a palette dict (see palettes.py). Layout,
spacing and typography are fixed; only the accent family of tokens
differs between the five accent palettes the user can pick in
Settings > Appearance.
"""
from string import Template

_TEMPLATE = Template("""
/* Global */
* {
    font-family: $font_sans;
    font-size: 13px;
}
QMainWindow, QWidget#centralWidget {
    background: $bg_page;
}

/* Sidebar */
QWidget#sidebar {
    background: $bg_sidebar;
    border-right: 1px solid $border;
}
QLabel#appTitle {
    font-size: 12px;
    font-weight: 500;
    color: $text_primary;
    padding: 16px 16px 10px;
}
QPushButton#navBtn {
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-radius: 0px;
    text-align: left;
    padding: 8px 16px;
    color: $text_secondary;
    font-size: 12.5px;
}
QPushButton#navBtn:hover {
    background: $bg_hover;
    color: $text_primary;
}
QPushButton#navBtn[active="true"] {
    border-left: 2px solid $accent;
    background: $bg_card;
    color: $text_primary;
    font-weight: 500;
}
QLabel#navSection {
    font-size: 10px;
    font-weight: 500;
    color: $text_faint;
    letter-spacing: 0.6px;
    padding: 14px 16px 4px;
}

/* Top bar */
QWidget#topbar {
    background: $bg_page;
    border-bottom: 1px solid $border;
}
QLabel#topbarTitle {
    font-size: 14px;
    font-weight: 500;
    color: $text_primary;
}
QLabel#topbarSub {
    font-size: 10.5px;
    color: $text_faint;
    font-family: $font_mono;
}

/* Buttons */
QPushButton {
    background: $bg_card;
    color: $text_secondary;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 6px 13px;
    font-size: 11.5px;
}
QPushButton:hover {
    background: $bg_hover;
    border-color: $border_stronger;
    color: $text_primary;
}
QPushButton:pressed {
    background: $bg_card_alt;
}
QPushButton#btnPrimary {
    background: $accent;
    color: $on_accent;
    border: 1px solid $accent;
    font-weight: 600;
}
QPushButton#btnPrimary:hover {
    background: $accent_hover;
    border-color: $accent_hover;
}
QPushButton#btnPrimary:pressed {
    background: $accent_pressed;
}
QPushButton#btnDanger {
    background: $danger_bg;
    color: $danger;
    border: 1px solid $danger_border;
}
QPushButton#btnDanger:hover {
    background: $danger_border;
}
QPushButton#btnWarning {
    background: $warning_bg;
    color: $warning;
    border: 1px solid $warning_border;
}
QPushButton#btnWarning:hover {
    background: $warning_border;
}

/* Metric cards */
QWidget#metricCard {
    background: $bg_card;
    border-radius: 7px;
}
QLabel#metricLabel {
    font-size: 10px;
    color: $text_muted;
}
QLabel#metricValue {
    font-size: 19px;
    font-weight: 600;
    color: $text_primary;
    font-family: $font_mono;
}
QLabel#metricSub {
    font-size: 10.5px;
    color: $text_faint;
}

/* Cache table */
QTableWidget {
    background: $bg_page;
    gridline-color: $border;
    border: 1px solid $border;
    border-radius: 7px;
    color: $text_secondary;
    selection-background-color: $bg_hover;
    selection-color: $text_primary;
    alternate-background-color: $bg_card_alt;
}
QTableWidget::item {
    padding: 6px 10px;
    border: none;
}
QTableWidget::item:hover {
    background: $bg_hover;
}
QHeaderView::section {
    background: $bg_sidebar;
    color: $text_faint;
    border: none;
    border-bottom: 1px solid $border;
    padding: 7px 10px;
    font-size: 10.5px;
    font-weight: 500;
}
QHeaderView::section:hover {
    background: $bg_card;
    color: $text_muted;
}

/* Scroll areas (fixes default light viewport background) */
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollArea > QWidget {
    background: transparent;
}

/* Scroll bars */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: $border_strong;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: $border_stronger;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    height: 6px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    background: $border_strong;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Detail panel */
QWidget#detailPanel {
    background: $bg_card_alt;
    border: 1px solid $border;
    border-radius: 7px;
}
QLabel#detailTitle {
    font-size: 13.5px;
    font-weight: 500;
    color: $text_primary;
}
QLabel#detailFieldLabel {
    font-size: 9.5px;
    color: $text_faint;
    letter-spacing: 0.4px;
}
QLabel#detailFieldValue {
    font-size: 13px;
    color: $text_secondary;
}
QLabel#detailLongDesc {
    font-size: 12.5px;
    color: $text_muted;
    line-height: 1.6;
}
QLabel#cmdLabel {
    font-family: $font_mono;
    font-size: 11.5px;
    color: $accent_text;
    background: $bg_sidebar;
    border: 1px solid $border;
    border-radius: 5px;
    padding: 7px 11px;
}

/* Risk badges */
QLabel#badgeSafe {
    background: $success_bg;
    color: $success;
    border: 1px solid $success_border;
    border-radius: 4px;
    padding: 2px 9px;
    font-size: 10.5px;
    font-weight: 600;
}
QLabel#badgeReview {
    background: $warning_bg;
    color: $warning;
    border: 1px solid $warning_border;
    border-radius: 4px;
    padding: 2px 9px;
    font-size: 10.5px;
    font-weight: 600;
}
QLabel#badgeDanger {
    background: $danger_bg;
    color: $danger;
    border: 1px solid $danger_border;
    border-radius: 4px;
    padding: 2px 9px;
    font-size: 10.5px;
    font-weight: 600;
}

/* Progress bar */
QProgressBar {
    background: $bg_card;
    border: 1px solid $border;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: $accent;
    border-radius: 4px;
}

/* Dialog / overlay */
QDialog {
    background: $bg_page;
    border: 1px solid $border_strong;
    border-radius: 10px;
}
QDialog QLabel {
    color: $text_secondary;
}

/* Search / input */
QLineEdit {
    background: $bg_input;
    border: 1px solid $border_strong;
    border-radius: 6px;
    color: $text_secondary;
    padding: 6px 10px;
    font-size: 11.5px;
}
QLineEdit:focus {
    border-color: $accent;
    background: $bg_card_alt;
}

/* Combo/Select */
QComboBox {
    background: $bg_input;
    border: 1px solid $border_strong;
    border-radius: 6px;
    color: $text_secondary;
    padding: 6px 10px;
    font-size: 11.5px;
}
QComboBox::drop-down { border: none; }
QComboBox:hover { border-color: $border_stronger; }
QComboBox QAbstractItemView {
    background: $bg_card;
    border: 1px solid $border_strong;
    color: $text_secondary;
    selection-background-color: $accent;
    selection-color: $on_accent;
}

/* Separator */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    border: none;
    background: $border;
    max-height: 1px;
}

/* Checkbox */
QCheckBox {
    color: $text_secondary;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid $border_strong;
    border-radius: 4px;
    background: $bg_input;
}
QCheckBox::indicator:checked {
    background: $accent;
    border-color: $accent;
}
QCheckBox:hover { color: $text_primary; }

/* Radio buttons */
QRadioButton {
    color: $text_secondary;
    spacing: 8px;
    font-size: 13px;
}
QRadioButton::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid $border_strong;
    border-radius: 8px;
    background: $bg_input;
}
QRadioButton::indicator:checked {
    background: $accent;
    border-color: $accent;
}
QRadioButton:hover { color: $text_primary; }

/* Tabs */
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent;
    color: $text_faint;
    border: none;
    padding: 8px 16px;
    font-size: 11.5px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: $text_primary;
    border-bottom: 2px solid $accent;
}
QTabBar::tab:hover {
    color: $text_secondary;
}

/* Lists */
QListWidget {
    background: $bg_input;
    border: 1px solid $border;
    border-radius: 6px;
    color: $text_secondary;
    font-family: $font_mono;
    font-size: 11.5px;
    padding: 4px;
}
QListWidget::item {
    padding: 4px 6px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background: $bg_hover;
    color: $text_primary;
}

/* Menus */
QMenu {
    background: $bg_card;
    border: 1px solid $border_strong;
    color: $text_secondary;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: $accent;
    color: $on_accent;
}
QMenu::separator {
    height: 1px;
    background: $border_strong;
    margin: 4px 8px;
}

/* Misc text helpers */
QLabel#sectionLabel {
    font-size: 12.5px;
    font-weight: 600;
    color: $text_secondary;
}
QLabel#kbdLabel {
    font-family: $font_mono;
    font-size: 11px;
    color: $accent_text;
    background: $bg_sidebar;
    border: 1px solid $border;
    border-radius: 4px;
    padding: 2px 8px;
}
QLabel#mutedText {
    color: $text_muted;
    font-size: 12px;
}

/* Tooltip */
QToolTip {
    background: $bg_card;
    color: $text_secondary;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11.5px;
}
""")


def build_stylesheet(palette: dict) -> str:
    return _TEMPLATE.substitute(**palette)
