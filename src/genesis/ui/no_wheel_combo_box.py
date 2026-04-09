from __future__ import annotations

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox, QWidget


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse-wheel input entirely."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()
