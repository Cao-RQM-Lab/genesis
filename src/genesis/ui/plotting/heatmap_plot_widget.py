from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from genesis.ui.no_wheel_combo_box import NoWheelComboBox


class HeatmapPlotWidget(QWidget):
    def __init__(
        self,
        title: str,
        xLabel: str,
        yLabel: str,
        xBounds: tuple[float, float] | None = None,
        yBounds: tuple[float, float] | None = None,
        xPointCount: int | None = None,
        yPointCount: int | None = None,
        allowPopout: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = str(title)
        self._xLabel = str(xLabel)
        self._yLabel = str(yLabel)
        self._xByKey: dict[str, float] = {}
        self._yByKey: dict[str, float] = {}
        self._zByKeyPair: dict[tuple[str, str], float] = {}
        self._xBounds = xBounds
        self._yBounds = yBounds
        self._gridCols: int = max(1, int(xPointCount or 1))
        self._gridRows: int = max(1, int(yPointCount or 1))
        self._allowPopout = bool(allowPopout)
        self._popupDialog: QDialog | None = None
        self._popupHeatmap: HeatmapPlotWidget | None = None

        layout = QVBoxLayout(self)
        self._controlsWidget = QWidget(self)
        controls = QHBoxLayout(self._controlsWidget)
        controls.setContentsMargins(0, 0, 0, 0)
        self.colormapCombo = NoWheelComboBox(self)
        for name in ("viridis", "plasma", "inferno", "magma", "cividis", "turbo"):
            self.colormapCombo.addItem(name, userData=name)
        controls.addWidget(self.colormapCombo)
        if self._allowPopout:
            self.popoutButton = QPushButton("Open Large View", self)
            self.popoutButton.clicked.connect(self._openPopoutWindow)
            controls.addWidget(self.popoutButton)
        controls.addStretch(1)
        layout.addWidget(self._controlsWidget)

        self.plotWidget = pg.PlotWidget(self)
        self.plotWidget.setTitle(self._title)
        self.plotWidget.setLabel("bottom", self._xLabel)
        self.plotWidget.setLabel("left", self._yLabel)
        self.plotWidget.showGrid(x=True, y=True, alpha=0.2)
        view = self.plotWidget.getViewBox()
        if self._allowPopout:
            view.setAspectLocked(True, ratio=1.0)
        else:
            view.setAspectLocked(False)
        view.enableAutoRange(x=False, y=False)
        if self._allowPopout:
            self.plotWidget.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
        else:
            self.plotWidget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
        if self._allowPopout:
            plotRow = QHBoxLayout()
            plotRow.setContentsMargins(0, 0, 0, 0)
            plotRow.addStretch(1)
            plotRow.addWidget(self.plotWidget)
            plotRow.addStretch(1)
            layout.addLayout(plotRow, 1)
        else:
            layout.addWidget(self.plotWidget, 1)

        self._image = pg.ImageItem()
        self.plotWidget.addItem(self._image)
        self._bar = pg.ColorBarItem(
            values=(0.0, 1.0), colorMap=pg.colormap.get("viridis")
        )
        self._bar.setImageItem(self._image)

        self.colormapCombo.currentIndexChanged.connect(self._onColormapChanged)
        if self._allowPopout:
            self._updateSquareViewport()

    def appendPoint(self, x: float, y: float, z: float) -> None:
        xKey = f"{float(x):.12g}"
        yKey = f"{float(y):.12g}"
        self._xByKey[xKey] = float(x)
        self._yByKey[yKey] = float(y)
        self._zByKeyPair[(xKey, yKey)] = float(z)
        self._updateImage()
        if self._popupHeatmap is not None:
            self._popupHeatmap.appendPoint(float(x), float(y), float(z))

    def clearData(self) -> None:
        self._xByKey.clear()
        self._yByKey.clear()
        self._zByKeyPair.clear()
        # Avoid empty-image auto-level edge cases in pyqtgraph.
        self._image.setImage(np.zeros((1, 1), dtype=np.float64), autoLevels=False)
        self._image.setRect(QRectF(-0.5, -0.5, 1.0, 1.0))
        if self._popupHeatmap is not None:
            self._popupHeatmap.clearData()

    def _onColormapChanged(self, _idx: int) -> None:
        name = str(self.colormapCombo.currentData() or "viridis")
        cmap = pg.colormap.get(name)
        self._image.setColorMap(cmap)
        self._bar.setColorMap(cmap)
        if self._popupHeatmap is not None:
            idx = self._popupHeatmap.colormapCombo.findData(name)
            if idx >= 0 and self._popupHeatmap.colormapCombo.currentIndex() != idx:
                self._popupHeatmap.colormapCombo.setCurrentIndex(idx)

    def _updateImage(self) -> None:
        xVals = sorted(self._xByKey.values())
        yVals = sorted(self._yByKey.values())
        if not xVals or not yVals:
            return
        xIndex = {f"{v:.12g}": i for i, v in enumerate(xVals)}
        yIndex = {f"{v:.12g}": i for i, v in enumerate(yVals)}
        # ImageItem expects first axis as X and second axis as Y.
        z = np.full((len(xVals), len(yVals)), np.nan, dtype=np.float64)
        for (xKey, yKey), value in self._zByKeyPair.items():
            xi = xIndex.get(xKey)
            yi = yIndex.get(yKey)
            if xi is None or yi is None:
                continue
            z[xi, yi] = value

        self._image.setImage(z, autoLevels=True)
        # Use real numeric sweep coordinates for axis scaling.
        if self._xBounds is not None:
            xMin = float(min(self._xBounds[0], self._xBounds[1]))
            xMax = float(max(self._xBounds[0], self._xBounds[1]))
            xStep = max(1e-12, xMax - xMin)
        else:
            xStep = self._estimateAxisStep(xVals)
            xMin = float(xVals[0]) - (xStep / 2.0)
            xMax = float(xVals[-1]) + (xStep / 2.0)
        if self._yBounds is not None:
            yMin = float(min(self._yBounds[0], self._yBounds[1]))
            yMax = float(max(self._yBounds[0], self._yBounds[1]))
            yStep = max(1e-12, yMax - yMin)
        else:
            yStep = self._estimateAxisStep(yVals)
            yMin = float(yVals[0]) - (yStep / 2.0)
            yMax = float(yVals[-1]) + (yStep / 2.0)
        width = max(xStep, xMax - xMin)
        height = max(yStep, yMax - yMin)
        self._image.setRect(QRectF(xMin, yMin, width, height))

        # Let pyqtgraph generate numeric ticks (avoids categorical string-like axis behavior).
        self.plotWidget.getAxis("bottom").setTicks([])
        self.plotWidget.getAxis("left").setTicks([])
        view = self.plotWidget.getViewBox()
        view.setRange(
            rect=QRectF(xMin, yMin, width, height),
            padding=0.0,
        )

    def _estimateAxisStep(self, values: list[float]) -> float:
        if len(values) < 2:
            return 1.0
        diffs = [abs(float(b) - float(a)) for a, b in zip(values[:-1], values[1:])]
        positive = [d for d in diffs if d > 0.0]
        if not positive:
            return 1.0
        return float(np.median(np.asarray(positive, dtype=np.float64)))

    def resizeEvent(self, event: QResizeEvent) -> None:
        if self._allowPopout:
            self._updateSquareViewport()
        super().resizeEvent(event)

    def _updateSquareViewport(self) -> None:
        margins = self.contentsMargins()
        availableWidth = max(
            120,
            self.width() - margins.left() - margins.right() - 12,
        )
        controlsHeight = self._controlsWidget.sizeHint().height()
        availableHeight = max(
            120,
            self.height() - margins.top() - margins.bottom() - controlsHeight - 16,
        )
        side = max(120, min(availableWidth, availableHeight))
        targetWidth = side
        targetHeight = side
        if (
            self.plotWidget.width() != targetWidth
            or self.plotWidget.height() != targetHeight
        ):
            self.plotWidget.setFixedSize(targetWidth, targetHeight)

    def _openPopoutWindow(self) -> None:
        if self._popupDialog is not None and self._popupDialog.isVisible():
            self._popupDialog.raise_()
            self._popupDialog.activateWindow()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self._title} - Large View")
        dialogLayout = QVBoxLayout(dialog)
        popupHeatmap = HeatmapPlotWidget(
            title=self._title,
            xLabel=self._xLabel,
            yLabel=self._yLabel,
            xBounds=self._xBounds,
            yBounds=self._yBounds,
            xPointCount=self._gridCols,
            yPointCount=self._gridRows,
            allowPopout=False,
            parent=dialog,
        )
        dialogLayout.addWidget(popupHeatmap)
        dialog.resize(980, 980)
        self._popupDialog = dialog
        self._popupHeatmap = popupHeatmap
        # Sync colormap and existing data.
        currentMap = str(self.colormapCombo.currentData() or "viridis")
        mapIdx = popupHeatmap.colormapCombo.findData(currentMap)
        if mapIdx >= 0:
            popupHeatmap.colormapCombo.setCurrentIndex(mapIdx)
        for (xKey, yKey), value in self._zByKeyPair.items():
            xVal = self._xByKey.get(xKey)
            yVal = self._yByKey.get(yKey)
            if xVal is None or yVal is None:
                continue
            popupHeatmap.appendPoint(float(xVal), float(yVal), float(value))
        dialog.finished.connect(self._onPopoutClosed)
        dialog.show()

    def _onPopoutClosed(self, _result: int) -> None:
        self._popupHeatmap = None
        self._popupDialog = None
