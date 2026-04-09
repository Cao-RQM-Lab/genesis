from __future__ import annotations

import unittest

from PySide6.QtWidgets import QApplication

from genesis.app.main_window import MainWindow


class MainWindowPlotResolutionTests(unittest.TestCase):
    _app: QApplication | None = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = MainWindow()

    def test_var_axis_resolution_unchanged(self) -> None:
        axis = {"type": "var", "instrumentId": "smu1", "key": "senseVoltageV"}
        self.window._latestValues[("smu1", "senseVoltageV")] = 1.23
        actual = self.window._resolveAxisValue(0, "x", axis)
        self.assertEqual(actual, 1.23)

    def test_time_axis_resolution_unchanged(self) -> None:
        axis = {"type": "time"}
        self.window._latestTimestamp = 42.5
        actual = self.window._resolveAxisValue(0, "x", axis)
        self.assertEqual(actual, 42.5)

    def test_expr_axis_resolution(self) -> None:
        axis = {"type": "expr", "expr": "smu1:senseVoltageV * 1e3"}
        self.window._latestValues[("smu1", "senseVoltageV")] = 0.002
        actual = self.window._resolveAxisValue(0, "y", axis)
        self.assertAlmostEqual(float(actual or 0.0), 2.0)

    def test_time_from_time_sweep_resolution(self) -> None:
        axis = {"type": "expr", "expr": "__time__:time * 2"}
        self.window._latestValues[("__time__", "time")] = 1.5
        actual = self.window._resolveAxisValue(0, "x", axis)
        self.assertAlmostEqual(float(actual or 0.0), 3.0)


if __name__ == "__main__":
    unittest.main()
