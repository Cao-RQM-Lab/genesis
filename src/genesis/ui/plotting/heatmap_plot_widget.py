from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from genesis.ui.no_wheel_combo_box import NoWheelComboBox


class HeatmapPlotWidget(QWidget):
    def __init__(
        self,
        title: str,
        xLabel: str,
        yLabel: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._xByKey: dict[str, float] = {}
        self._yByKey: dict[str, float] = {}
        self._zByKeyPair: dict[tuple[str, str], float] = {}

        layout = QVBoxLayout(self)
        self._controlsWidget = QWidget(self)
        controls = QHBoxLayout(self._controlsWidget)
        controls.setContentsMargins(0, 0, 0, 0)
        self.colormapCombo = NoWheelComboBox(self)
        for name in ("viridis", "plasma", "inferno", "magma", "cividis", "turbo"):
            self.colormapCombo.addItem(name, userData=name)
        controls.addWidget(self.colormapCombo)
        controls.addStretch(1)
        layout.addWidget(self._controlsWidget)

        self.plotWidget = pg.PlotWidget(self)
        self.plotWidget.setTitle(title)
        self.plotWidget.setLabel("bottom", xLabel)
        self.plotWidget.setLabel("left", yLabel)
        self.plotWidget.showGrid(x=True, y=True, alpha=0.2)
        view = self.plotWidget.getViewBox()
        view.setAspectLocked(True, ratio=1.0)
        view.enableAutoRange(x=False, y=False)
        self.plotWidget.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        plotRow = QHBoxLayout()
        plotRow.setContentsMargins(0, 0, 0, 0)
        plotRow.addStretch(1)
        plotRow.addWidget(self.plotWidget)
        plotRow.addStretch(1)
        layout.addLayout(plotRow, 1)

        self._image = pg.ImageItem()
        self.plotWidget.addItem(self._image)
        self._bar = pg.ColorBarItem(
            values=(0.0, 1.0), colorMap=pg.colormap.get("viridis")
        )
        self._bar.setImageItem(self._image)

        self.colormapCombo.currentIndexChanged.connect(self._onColormapChanged)
        self._updateSquareViewport()

    def appendPoint(self, x: float, y: float, z: float) -> None:
        xKey = f"{float(x):.12g}"
        yKey = f"{float(y):.12g}"
        self._xByKey[xKey] = float(x)
        self._yByKey[yKey] = float(y)
        self._zByKeyPair[(xKey, yKey)] = float(z)
        self._updateImage()

    def clearData(self) -> None:
        self._xByKey.clear()
        self._yByKey.clear()
        self._zByKeyPair.clear()
        self._image.setImage(np.asarray([[]], dtype=np.float64), autoLevels=True)

    def _onColormapChanged(self, _idx: int) -> None:
        name = str(self.colormapCombo.currentData() or "viridis")
        cmap = pg.colormap.get(name)
        self._image.setColorMap(cmap)
        self._bar.setColorMap(cmap)

    def _updateImage(self) -> None:
        xVals = sorted(self._xByKey.values())
        yVals = sorted(self._yByKey.values())
        if not xVals or not yVals:
            return
        xIndex = {f"{v:.12g}": i for i, v in enumerate(xVals)}
        yIndex = {f"{v:.12g}": i for i, v in enumerate(yVals)}
        z = np.full((len(yVals), len(xVals)), np.nan, dtype=np.float64)
        for (xKey, yKey), value in self._zByKeyPair.items():
            xi = xIndex.get(xKey)
            yi = yIndex.get(yKey)
            if xi is None or yi is None:
                continue
            z[yi, xi] = value

        self._image.setImage(z, autoLevels=True)
        # Render on a unit grid so each heatmap cell is square by default.
        width = float(len(xVals))
        height = float(len(yVals))
        self._image.setRect(QRectF(-0.5, -0.5, width, height))

        # Force equal numeric span on both axes (same scale range).
        span = max(width, height)
        half = span / 2.0
        xCenter = (width - 1.0) / 2.0
        yCenter = (height - 1.0) / 2.0
        view = self.plotWidget.getViewBox()
        view.setRange(
            rect=QRectF(xCenter - half, yCenter - half, span, span),
            padding=0.0,
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
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
        if self.plotWidget.width() != side or self.plotWidget.height() != side:
            self.plotWidget.setFixedSize(side, side)
