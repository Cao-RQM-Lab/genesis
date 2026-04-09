from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget


class XyPlotWidget(QWidget):
    def __init__(
        self,
        title: str,
        xLabel: str,
        yLabel: str,
        ySeriesLabels: list[str] | None = None,
        maxPoints: int = 5000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.maxPoints = maxPoints
        self.ySeriesLabels = list(ySeriesLabels or ["Y"])

        self._x = np.empty(maxPoints, dtype=np.float64)
        self._yBySeries: dict[str, np.ndarray] = {
            key: np.empty(maxPoints, dtype=np.float64) for key in self.ySeriesLabels
        }
        self._count = 0
        self._nextIndex = 0

        layout = QVBoxLayout(self)
        self.plotWidget = pg.PlotWidget(self)
        self.plotWidget.setTitle(title)
        self.plotWidget.showGrid(x=True, y=True, alpha=0.2)
        self.plotWidget.setLabel("bottom", xLabel)
        self.plotWidget.setLabel("left", yLabel)
        self.plotWidget.addLegend()
        layout.addWidget(self.plotWidget)

        palette = [
            "#63b3ff",
            "#ff9f68",
            "#66d9a3",
            "#ff6fae",
            "#f5d547",
            "#b197fc",
            "#4dd0e1",
            "#ff7a7a",
        ]
        self._curveBySeries: dict[str, pg.PlotDataItem] = {}
        for idx, key in enumerate(self.ySeriesLabels):
            color = palette[idx % len(palette)]
            self._curveBySeries[key] = self.plotWidget.plot(
                [],
                [],
                name=key,
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=color,
                symbolPen=color,
            )

    def appendPoint(self, x: float, yValuesBySeries: dict[str, float]) -> None:
        self._x[self._nextIndex] = float(x)
        for key in self.ySeriesLabels:
            self._yBySeries[key][self._nextIndex] = float(
                yValuesBySeries.get(key, float("nan"))
            )
        self._nextIndex = (self._nextIndex + 1) % self.maxPoints
        if self._count < self.maxPoints:
            self._count += 1

        xData = self._orderedSeries(self._x)
        for key in self.ySeriesLabels:
            yData = self._orderedSeries(self._yBySeries[key])
            self._curveBySeries[key].setData(xData, yData)

    def _orderedSeries(self, series: np.ndarray) -> np.ndarray:
        if self._count == 0:
            return series[:0]
        if self._count < self.maxPoints:
            return series[: self._count]
        if self._nextIndex == 0:
            return series
        return np.concatenate((series[self._nextIndex :], series[: self._nextIndex]))
