from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

APP_STYLE_SHEET = """
QWidget {
    background-color: #1f232a;
    color: #e8eaed;
    font-size: 13px;
}

QMainWindow {
    background-color: #1b1f26;
}

QTabWidget::pane {
    border: 1px solid #303845;
    border-radius: 8px;
    background: #1f232a;
    top: -1px;
}

QTabBar::tab {
    background: #2a2f38;
    color: #cfd8e3;
    border: 1px solid #303845;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 12px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #323a46;
    color: #ffffff;
}

QGroupBox {
    border: 1px solid #323a46;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 12px;
    background: #252b34;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #9fc2ff;
}

QPushButton {
    background-color: #2d3642;
    border: 1px solid #3e4a5b;
    border-radius: 6px;
    padding: 6px 10px;
}

QPushButton:hover {
    background-color: #3a4452;
}

QPushButton:pressed {
    background-color: #455265;
}

QPushButton:disabled {
    color: #8b96a6;
    background-color: #252b33;
    border-color: #303845;
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QListWidget {
    background: #20262e;
    border: 1px solid #394353;
    border-radius: 6px;
    padding: 5px 8px;
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    min-width: 280px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid #4a566a;
    background-color: #2d3642;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox:hover {
    border-color: #54749d;
}

QComboBox:focus {
    border-color: #6aa9ff;
}

QComboBox::down-arrow {
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 7px solid #dce2ea;
    margin-right: 2px;
}

QComboBox:on {
    background: #27303b;
}

QComboBox QAbstractItemView {
    border: 1px solid #4a566a;
    background: #1f252d;
    selection-background-color: #3f5875;
    selection-color: #ffffff;
    padding: 4px;
}

QListWidget::item {
    padding: 4px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background: #3f5875;
    color: #ffffff;
}

QScrollArea {
    border: none;
    background: transparent;
}

QLabel {
    color: #dce2ea;
}

QProgressBar {
    border: 1px solid #3b4656;
    border-radius: 6px;
    text-align: center;
    background: #20262e;
    min-height: 18px;
}

QProgressBar::chunk {
    border-radius: 5px;
    background-color: #4e9eff;
}
"""


def applyAppTheme(app: QApplication) -> None:
    app.setStyleSheet(APP_STYLE_SHEET)
    pg.setConfigOptions(antialias=True, background="#1d222a", foreground="#dce2ea")
