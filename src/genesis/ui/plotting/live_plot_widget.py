from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget


class LivePlotWidget(QWidget):
    def __init__(
        self,
        title: str,
        signalKeys: list[str],
        maxPoints: int = 2000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.signalKeys = signalKeys
        self.maxPoints = maxPoints

        self._t = np.empty(maxPoints, dtype=np.float64)
        self._yByKey: dict[str, np.ndarray] = {
            key: np.empty(maxPoints, dtype=np.float64) for key in signalKeys
        }
        self._count = 0
        self._nextIndex = 0

        layout = QVBoxLayout(self)
        self.plotWidget = pg.PlotWidget(self)
        self.plotWidget.setTitle(title)
        self.plotWidget.showGrid(x=True, y=True, alpha=0.2)
        self.plotWidget.addLegend()
        layout.addWidget(self.plotWidget)

        self._curveByKey: dict[str, pg.PlotDataItem] = {}
        for key in signalKeys:
            curve = self.plotWidget.plot([], [], name=key)
            self._curveByKey[key] = curve

    def appendSample(self, timestamp: float, values: dict[str, float]) -> None:
        self._t[self._nextIndex] = float(timestamp)
        for key in self.signalKeys:
            self._yByKey[key][self._nextIndex] = float(values.get(key, float("nan")))

        self._nextIndex = (self._nextIndex + 1) % self.maxPoints
        if self._count < self.maxPoints:
            self._count += 1

        t = self._orderedSeries(self._t)
        for key in self.signalKeys:
            y = self._orderedSeries(self._yByKey[key])
            self._curveByKey[key].setData(t, y)

    def _orderedSeries(self, series: np.ndarray) -> np.ndarray:
        if self._count == 0:
            return series[:0]
        if self._count < self.maxPoints:
            return series[: self._count]
        if self._nextIndex == 0:
            return series
        return np.concatenate((series[self._nextIndex :], series[: self._nextIndex]))
