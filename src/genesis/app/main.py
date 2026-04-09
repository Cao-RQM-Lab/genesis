from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from genesis.app.main_window import MainWindow
from genesis.app.user_dirs import ensure_genesis_user_directories
from genesis.ui.theme import applyAppTheme


def main() -> None:
    app = QApplication(sys.argv)
    ensure_genesis_user_directories()
    applyAppTheme(app)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
