from __future__ import annotations

import json
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QFileDialog,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from genesis.app.user_dirs import genesis_jobs_dir, genesis_runs_dir
from genesis.core.job.abort_controller import AbortController
from genesis.core.job.model import JobModel
from genesis.core.instrument.discovery import loadBuiltInInstruments
from genesis.core.instrument.registry import InstrumentRegistry
from genesis.core.runtime.expression_eval import (
    CompiledExpression,
    ExpressionError,
    compileExpression,
    evaluateExpression,
)
from genesis.core.runtime.acquisition_worker import (
    AcquisitionWorker,
    startAcquisitionThread,
)
from genesis.core.transport.transport_factory import createTransport
from genesis.ui.job_builder.job_builder_widget import JobBuilderWidget
from genesis.ui.plotting.heatmap_plot_widget import HeatmapPlotWidget
from genesis.ui.plotting.xy_plot_widget import XyPlotWidget


class MainWindow(QMainWindow):
    """
    Minimal main window with a prominent Abort button and job loading hook.
    """

    def __init__(
        self,
        abortController: AbortController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.abortController = abortController or AbortController()
        self.currentJob: JobModel | None = None
        self._acqThread = None
        self._acqWorker = None
        self._plotConfigs: list[dict[str, Any]] = []
        self._compiledExprByAxis: dict[tuple[int, str], CompiledExpression] = {}
        self._lastExprErrorTimeByAxis: dict[tuple[int, str], float] = {}
        self._plotWidgetsByIndex: dict[int, QWidget] = {}
        self._latestValues: dict[tuple[str, str], float] = {}
        self._latestTimestamp: float = 0.0
        self._runStartUnixTimestamp: float | None = None
        self._dataFileHandle = None
        self._dataCsvWriter = None
        self._dataFilePath: Path | None = None
        self._dataBasePath: Path | None = None
        self._dataExportFormat: str = "csv"
        self._currentSweepFilePath: Path | None = None
        self._currentSweepRows: list[dict[str, float]] = []
        self._currentSweepLabel: str = ""
        self._dataColumnKeys: list[tuple[str, str]] = []
        self._npyCheckpointEveryRows: int = 100
        self._initializedInstrumentsById: dict[str, Any] = {}
        self._initializedMeasurementKeysByInstrumentId: dict[str, list[str]] = {}
        self._rawLogKeysByInstrumentId: dict[str, set[str]] = {}
        self._initializedSweeps: list[dict[str, Any]] = []
        self._initializedJobId: str | None = None

        self._setupUi()

    def _setupUi(self) -> None:
        self.setWindowTitle("Genesis")

        rootWidget = QWidget(self)
        rootLayout = QVBoxLayout(rootWidget)

        tabWidget = QTabWidget(rootWidget)
        runTab = QWidget(tabWidget)
        jobBuilderTab = QWidget(tabWidget)

        tabWidget.addTab(runTab, "Run")
        tabWidget.addTab(jobBuilderTab, "Job Builder")

        # ---- Run tab ----
        runLayout = QVBoxLayout(runTab)
        jobInfoRow = QHBoxLayout()
        jobInfoRow.addWidget(QLabel("Job Name", runTab))
        self.jobNameLabel = QLabel("(none)", runTab)
        self.jobNameLabel.setTextInteractionFlags(
            self.jobNameLabel.textInteractionFlags()
        )
        self.jobNameLabel.setStyleSheet("color: #666;")
        jobInfoRow.addWidget(self.jobNameLabel)
        jobInfoRow.addSpacing(16)
        jobInfoRow.addWidget(QLabel("Job ID", runTab))
        self.jobIdValueLabel = QLabel("(none)", runTab)
        self.jobIdValueLabel.setTextInteractionFlags(
            self.jobIdValueLabel.textInteractionFlags()
        )
        self.jobIdValueLabel.setStyleSheet("color: #666;")
        jobInfoRow.addWidget(self.jobIdValueLabel)
        jobInfoRow.addStretch(1)
        self.statusLabel = QLabel("No Job Loaded.", runTab)
        self.runPlotsContainer = QWidget(runTab)
        self.runPlotsLayout = QVBoxLayout(self.runPlotsContainer)
        self.runPlotsLayout.setContentsMargins(0, 0, 0, 0)
        self.runPlotsSplitter = QSplitter(
            Qt.Orientation.Vertical, self.runPlotsContainer
        )
        self.runPlotsSplitter.setChildrenCollapsible(False)
        self.runPlotsLayout.addWidget(self.runPlotsSplitter)
        self.runPlotsScroll = QScrollArea(runTab)
        self.runPlotsScroll.setWidgetResizable(True)
        self.runPlotsScroll.setWidget(self.runPlotsContainer)

        buttonRow = QHBoxLayout()
        self.loadJobButton = QPushButton("Load Job (JSON)...", runTab)
        self.initializeButton = QPushButton("Initialize", runTab)
        self.startRunButton = QPushButton("Start Sweep", runTab)
        self.stopRunButton = QPushButton("Stop", runTab)
        self.abortButton = QPushButton("Abort", runTab)
        self.abortButton.setStyleSheet(
            "font-weight: 700; color: #ffffff; background-color: #a13333; border-color: #bf4a4a;"
        )

        buttonRow.addWidget(self.loadJobButton)
        buttonRow.addWidget(self.initializeButton)
        buttonRow.addWidget(self.startRunButton)
        buttonRow.addWidget(self.stopRunButton)
        buttonRow.addWidget(self.abortButton)

        self.sweepProgressLabel = QLabel("Sweep Progress: Idle", runTab)
        self.sweepProgressBar = QProgressBar(runTab)
        self.sweepProgressBar.setRange(0, 1000)
        self.sweepProgressBar.setValue(0)

        runLayout.addLayout(jobInfoRow)
        runLayout.addWidget(self.statusLabel)
        runLayout.addLayout(buttonRow)
        runLayout.addWidget(self.sweepProgressLabel)
        runLayout.addWidget(self.sweepProgressBar)
        runLayout.addWidget(self.runPlotsScroll)
        runLayout.setStretchFactor(self.runPlotsScroll, 1)

        # ---- Job builder tab ----
        instrumentRegistry = InstrumentRegistry()
        loadBuiltInInstruments(instrumentRegistry)
        jobBuilderLayout = QVBoxLayout(jobBuilderTab)
        jobBuilderLayout.addWidget(
            JobBuilderWidget(instrumentRegistry, parent=jobBuilderTab)
        )

        rootLayout.addWidget(tabWidget)
        self.setCentralWidget(rootWidget)

        self.loadJobButton.clicked.connect(self._onLoadJobClicked)
        self.initializeButton.clicked.connect(self._onInitializeClicked)
        self.startRunButton.clicked.connect(self._onStartClicked)
        self.stopRunButton.clicked.connect(self._onStopClicked)
        self.abortButton.clicked.connect(self._onAbortClicked)

    def _onLoadJobClicked(self) -> None:
        pathStr = QFileDialog.getOpenFileName(
            self,
            "Open Job JSON",
            str(genesis_jobs_dir()),
            filter="JSON files (*.json)",
        )[0]
        if not pathStr:
            return
        self.loadJobFromPath(Path(pathStr))

    def _onAbortClicked(self) -> None:
        self.abortController.requestAbort()
        self._stopAcquisition()
        self._applySafeStateToInitializedInstruments()
        self._checkpointCurrentSweepFile()
        self.statusLabel.setText("Abort complete. Safe state applied.")

    def _onStartClicked(self) -> None:
        if self.currentJob is None:
            self.statusLabel.setText("Load a Job First.")
            return
        currentJobId = str(self.currentJob.rawDefinition.get("jobId", ""))
        if self._initializedJobId != currentJobId:
            self.statusLabel.setText("Initialize Instruments First.")
            return
        self._startSweepRun()

    def _onInitializeClicked(self) -> None:
        if self.currentJob is None:
            self.statusLabel.setText("Load a Job First.")
            return
        self._initializeInstrumentsFromJob(self.currentJob.rawDefinition)

    def _onStopClicked(self) -> None:
        self._stopAcquisition()

    def _clearPlots(self) -> None:
        self._plotConfigs.clear()
        self._compiledExprByAxis.clear()
        self._lastExprErrorTimeByAxis.clear()
        self._plotWidgetsByIndex.clear()
        self._latestValues.clear()
        self._latestTimestamp = 0.0
        while self.runPlotsSplitter.count() > 0:
            widget = self.runPlotsSplitter.widget(0)
            if widget is None:
                break
            widget.setParent(None)

    def loadJobFromPath(self, path: Path) -> None:
        """
        Load a job definition from the given JSON file path.
        """
        # TODO: replace with robust validation and error handling.
        try:
            text = path.read_text(encoding="utf8")
            payload: dict[str, Any] = json.loads(text)
        except Exception:
            self.statusLabel.setText(f"Failed to load job: {path}")
            return

        self._stopAcquisition()
        self._closeInitializedInstruments()
        self._initializedJobId = None
        self.currentJob = JobModel.fromJson(payload)
        self.jobNameLabel.setText(path.name)
        self.jobIdValueLabel.setText(self.currentJob.jobId)
        self.statusLabel.setText("Job ready. Initialize Instruments.")

        self._clearPlots()
        self._setupPlotsFromJob(payload)
        self.sweepProgressLabel.setText("Sweep Progress: Idle")
        self.sweepProgressBar.setValue(0)

    def _setupPlotsFromJob(self, jobDefinition: dict[str, Any]) -> None:
        self._plotConfigs = list(jobDefinition.get("plots", []))
        for idx, plotDef in enumerate(self._plotConfigs):
            title = str(plotDef.get("title", "")).strip() or f"Plot {idx + 1}"
            renderMode = str(plotDef.get("renderMode", "scatter") or "scatter")
            if renderMode == "heatmap":
                xDef, hyDef = self._normalizedHeatmapAxisDefs(plotDef, jobDefinition)
            else:
                xDef = plotDef.get("x", {})
                hyDef = plotDef.get("heatmapY", {})
            ySeriesDefs = self._getYSeriesDefs(plotDef)

            xLabel = (
                "time" if isinstance(xDef, dict) and xDef.get("type") == "time" else "x"
            )
            if isinstance(xDef, dict) and xDef.get("type") == "var":
                xLabel = f"{xDef.get('instrumentId')}:{xDef.get('key')}"
            if isinstance(xDef, dict) and xDef.get("type") == "expr":
                xLabel = str(xDef.get("expr", "")).strip() or "expr"

            yLabel = "Y values"
            ySeriesLabels: list[str] = []
            for yIdx, yDef in enumerate(ySeriesDefs, start=1):
                label = self._seriesDisplayLabel(yDef, yIdx)
                ySeriesLabels.append(label)
            if renderMode != "heatmap":
                if len(ySeriesLabels) == 1:
                    yLabel = ySeriesLabels[0]
                elif len(ySeriesLabels) > 1:
                    yLabel = "Values"

            self._compileAxisExpression(idx, "x", xDef)
            if renderMode == "heatmap":
                self._compileAxisExpression(idx, "hy", hyDef)
                if ySeriesDefs:
                    self._compileAxisExpression(idx, "y:0", ySeriesDefs[0])
            else:
                for yIdx, yDef in enumerate(ySeriesDefs):
                    self._compileAxisExpression(idx, f"y:{yIdx}", yDef)

            if renderMode == "heatmap":
                if isinstance(xDef, dict) and xDef.get("type") == "var":
                    xAxisLabel = f"{xDef.get('instrumentId')}:{xDef.get('key')}"
                else:
                    xAxisLabel = (
                        str(xDef.get("expr", "")).strip()
                        if isinstance(xDef, dict)
                        else "x"
                    )
                if isinstance(hyDef, dict) and hyDef.get("type") == "var":
                    yAxisLabel = f"{hyDef.get('instrumentId')}:{hyDef.get('key')}"
                else:
                    yAxisLabel = (
                        str(hyDef.get("expr", "")).strip()
                        if isinstance(hyDef, dict)
                        else "y"
                    )
                xAxisLabel = xAxisLabel or "x"
                yAxisLabel = yAxisLabel or "y"
                widget = HeatmapPlotWidget(
                    title=title,
                    xLabel=xAxisLabel,
                    yLabel=yAxisLabel,
                    parent=self.runPlotsContainer,
                )
            else:
                widget = XyPlotWidget(
                    title=title,
                    xLabel=xLabel,
                    yLabel=yLabel,
                    ySeriesLabels=ySeriesLabels,
                    parent=self.runPlotsContainer,
                )
            widget.setMinimumHeight(240)
            self._plotWidgetsByIndex[idx] = widget
            self.runPlotsSplitter.addWidget(widget)

        if self.runPlotsSplitter.count() > 0:
            self.runPlotsSplitter.setSizes([240] * self.runPlotsSplitter.count())

    def _buildRuntimeFromJob(
        self, jobDefinition: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, list[str]], list[dict[str, Any]]]:
        registry = InstrumentRegistry()
        loadBuiltInInstruments(registry)

        instrumentsById: dict[str, Any] = {}
        requiredKeysByInstrumentId: dict[str, set[str]] = {}

        # Collect signal keys required by plot definitions.
        for plotDef in jobDefinition.get("plots", []):
            renderMode = str(plotDef.get("renderMode", "scatter") or "scatter")
            if renderMode == "heatmap":
                xDef, hyDef = self._normalizedHeatmapAxisDefs(plotDef, jobDefinition)
                axisDefs: list[Any] = [xDef, hyDef]
            else:
                axisDefs = [plotDef.get("x", {})]
            ySeries = plotDef.get("ySeries", [])
            if isinstance(ySeries, list) and ySeries:
                if renderMode == "heatmap":
                    axisDefs.append(ySeries[0])
                else:
                    axisDefs.extend(ySeries)
            else:
                axisDefs.append(plotDef.get("y", {}))
            for axisDef in axisDefs:
                if not isinstance(axisDef, dict):
                    continue
                if axisDef.get("type") != "var":
                    if axisDef.get("type") == "expr":
                        expr = str(axisDef.get("expr", "")).strip()
                        if not expr:
                            continue
                        try:
                            compiled = compileExpression(expr)
                        except ExpressionError:
                            # Keep runtime resilient; UI should catch this first.
                            continue
                        for instId, key in compiled.dependencies:
                            if not instId or not key:
                                continue
                            requiredKeysByInstrumentId.setdefault(instId, set()).add(
                                key
                            )
                    continue
                instId = str(axisDef.get("instrumentId", ""))
                key = str(axisDef.get("key", ""))
                if not instId or not key:
                    continue
                requiredKeysByInstrumentId.setdefault(instId, set()).add(key)

        for instDef in jobDefinition.get("instruments", []):
            instrumentId = str(instDef.get("id", ""))
            instrumentTypeKey = str(instDef.get("type", ""))
            transportKey = str(instDef.get("transport", "visa"))
            address = str(instDef.get("address", ""))
            jobConfig = dict(instDef.get("config", {}))

            if not instrumentId or not instrumentTypeKey:
                continue

            transport = createTransport(
                transportKey=transportKey, resourceName=address, settings=None
            )
            transport.open()

            instrument = registry.createInstrument(
                instrumentTypeKey,
                name=instrumentId,
                transport=transport,
                metadata={
                    "type": instrumentTypeKey,
                    "safeConfig": dict(instDef.get("safeConfig", {})),
                },
                jobConfig=jobConfig,
            )

            instrumentsById[instrumentId] = instrument

            userMeasurementKeys = set(instDef.get("measurements", []))
            plotKeys = requiredKeysByInstrumentId.get(instrumentId, set())
            required = sorted(
                {str(k) for k in (userMeasurementKeys | plotKeys) if str(k)}
            )
            requiredKeysByInstrumentId.setdefault(instrumentId, set()).update(required)

        return (
            instrumentsById,
            {
                instId: sorted(keys)
                for instId, keys in requiredKeysByInstrumentId.items()
            },
            list(jobDefinition.get("sweeps", [])),
        )

    def _initializeInstrumentsFromJob(self, jobDefinition: dict[str, Any]) -> None:
        self._stopAcquisition()
        self._closeInitializedInstruments()
        self._initializedJobId = None
        self.sweepProgressLabel.setText("Sweep Progress: Initializing")
        self.sweepProgressBar.setValue(0)

        try:
            (
                instrumentsById,
                measurementKeysByInstrumentId,
                sweeps,
            ) = self._buildRuntimeFromJob(jobDefinition)
        except Exception as exc:
            self.statusLabel.setText(f"Initialize failed: {exc}")
            return

        # Apply all configured instrument values.
        for instDef in jobDefinition.get("instruments", []):
            instrumentId = str(instDef.get("id", ""))
            instrument = instrumentsById.get(instrumentId)
            if instrument is None:
                continue

            for key, value in dict(instDef.get("config", {})).items():
                try:
                    instrument.applyConfigValue(str(key), value)
                except Exception as exc:
                    self.statusLabel.setText(
                        f"Initialize failed at {instrumentId}:{key}: {exc}"
                    )
                    self._closeInitializedInstruments()
                    return

            try:
                instrument.initialize()
            except NotImplementedError:
                pass
            except Exception as exc:
                self.statusLabel.setText(f"Initialize failed at {instrumentId}: {exc}")
                self._closeInitializedInstruments()
                return

        # Initialize each sweep variable to its first point.
        for sweep in sweeps:
            instId = str(sweep.get("instrumentId", ""))
            key = str(sweep.get("key", ""))
            if not instId or not key:
                continue
            instrument = instrumentsById.get(instId)
            if instrument is None:
                continue
            values = self._buildSweepValues(sweep)
            if len(values) == 0:
                continue
            try:
                instrument.applyConfigValue(key, values[0])
            except Exception as exc:
                self.statusLabel.setText(
                    f"Initialize failed at sweep {instId}:{key}: {exc}"
                )
                self._closeInitializedInstruments()
                return
            self._latestValues[(instId, key)] = float(values[0])

        self._initializedInstrumentsById = instrumentsById
        self._initializedMeasurementKeysByInstrumentId = measurementKeysByInstrumentId
        rawLogKeysByInstrumentId: dict[str, set[str]] = {}
        for instId, keys in measurementKeysByInstrumentId.items():
            rawLogKeysByInstrumentId[instId] = {str(k) for k in keys if str(k)}
        for sweep in sweeps:
            instId = str(sweep.get("instrumentId", ""))
            key = str(sweep.get("key", ""))
            if not instId or not key:
                continue
            rawLogKeysByInstrumentId.setdefault(instId, set()).add(key)
        self._rawLogKeysByInstrumentId = rawLogKeysByInstrumentId
        self._initializedSweeps = sweeps
        self._initializedJobId = str(jobDefinition.get("jobId", ""))
        self.statusLabel.setText("Initialization Complete. Ready to Start Sweep.")
        self.sweepProgressLabel.setText("Sweep Progress: Ready")
        self.sweepProgressBar.setValue(0)

    def _startSweepRun(self) -> None:
        self._stopAcquisition()
        self._runStartUnixTimestamp = datetime.now().timestamp()
        if not self._initializedInstrumentsById:
            self.statusLabel.setText("Initialize Instruments First.")
            return
        jobDefinition = self.currentJob.rawDefinition if self.currentJob else {}
        exportTarget = self._selectDataExportTarget(jobDefinition)
        if exportTarget is None:
            self.statusLabel.setText("Sweep start cancelled (no data file selected).")
            return
        targetPath, exportFormat = exportTarget
        self._prepareDataExport(targetPath, exportFormat)
        if not self._initializedSweeps:
            self._startSweepDataFile("continuous")

        worker = AcquisitionWorker(
            instrumentsById=self._initializedInstrumentsById,
            measurementKeysByInstrumentId=self._initializedMeasurementKeysByInstrumentId,
            sweeps=self._initializedSweeps,
            intervalSeconds=0.2,
        )
        thread, worker = startAcquisitionThread(worker)
        worker.sampleEmitted.connect(self._onSampleEmitted)
        worker.statusMessage.connect(self.statusLabel.setText)
        worker.sweepProgress.connect(self._onSweepProgress)

        self._acqThread = thread
        self._acqWorker = worker
        thread.start()

    def _stopAcquisition(self) -> None:
        if self._acqWorker is not None:
            self._acqWorker.requestStop()
        if self._acqThread is not None:
            self._acqThread.quit()
            self._acqThread.wait(2000)
        self._acqWorker = None
        self._acqThread = None
        self._closeDataLogFile()
        self._runStartUnixTimestamp = None

    def _closeInitializedInstruments(self) -> None:
        for instrument in self._initializedInstrumentsById.values():
            try:
                instrument.transport.close()
            except Exception:
                pass
        self._initializedInstrumentsById = {}
        self._initializedMeasurementKeysByInstrumentId = {}
        self._rawLogKeysByInstrumentId = {}
        self._initializedSweeps = []

    def _applySafeStateToInitializedInstruments(self) -> None:
        for instrumentId, instrument in self._initializedInstrumentsById.items():
            try:
                instrument.applySafeState()
            except Exception as exc:
                self.statusLabel.setText(
                    f"Abort warning: safe state failed for {instrumentId}: {exc}"
                )

    def closeEvent(self, event: QCloseEvent) -> None:
        # Best-effort durability on app close.
        self._stopAcquisition()
        self._closeInitializedInstruments()
        super().closeEvent(event)

    def _onSampleEmitted(
        self, timestamp: float, valuesByInstrumentId: dict[str, dict[str, float]]
    ) -> None:
        self._latestTimestamp = float(timestamp)
        for instrumentId, values in valuesByInstrumentId.items():
            for key, val in values.items():
                self._latestValues[(str(instrumentId), str(key))] = float(val)
        self._appendDataRow(timestamp, valuesByInstrumentId)

        for idx, plotDef in enumerate(self._plotConfigs):
            widget = self._plotWidgetsByIndex.get(idx)
            if widget is None:
                continue
            renderMode = str(plotDef.get("renderMode", "scatter") or "scatter")
            if renderMode == "heatmap":
                xDef, hyDef = self._normalizedHeatmapAxisDefs(
                    plotDef,
                    self.currentJob.rawDefinition if self.currentJob else {},
                )
                xCoord = self._resolveAxisValue(idx, "x", xDef)
                yCoord = self._resolveAxisValue(idx, "hy", hyDef)
                if xCoord is None or yCoord is None:
                    continue
                ySeriesDefs = self._getYSeriesDefs(plotDef)
                if len(ySeriesDefs) != 1:
                    continue
                if not ySeriesDefs:
                    continue
                zVal = self._resolveAxisValue(idx, "y:0", ySeriesDefs[0])
                if zVal is None or not isinstance(widget, HeatmapPlotWidget):
                    continue
                widget.appendPoint(float(xCoord), float(yCoord), float(zVal))
                continue

            xDef = plotDef.get("x", {})
            ySeriesDefs = self._getYSeriesDefs(plotDef)

            xVal = self._resolveAxisValue(idx, "x", xDef)
            if xVal is None:
                continue
            yValues: dict[str, float] = {}
            anyDefined = False
            for yIdx, yDef in enumerate(ySeriesDefs, start=1):
                name = self._seriesDisplayLabel(yDef, yIdx)
                yVal = self._resolveAxisValue(idx, f"y:{yIdx-1}", yDef)
                if yVal is not None:
                    anyDefined = True
                    yValues[name] = float(yVal)
            if not anyDefined:
                continue
            if isinstance(widget, XyPlotWidget):
                widget.appendPoint(float(xVal), yValues)

    def _compileAxisExpression(self, plotIdx: int, axisKey: str, axisDef: Any) -> None:
        if not isinstance(axisDef, dict) or axisDef.get("type") != "expr":
            self._compiledExprByAxis.pop((plotIdx, axisKey), None)
            return
        expr = str(axisDef.get("expr", "")).strip()
        if not expr:
            self._compiledExprByAxis.pop((plotIdx, axisKey), None)
            return
        try:
            self._compiledExprByAxis[(plotIdx, axisKey)] = compileExpression(expr)
        except ExpressionError:
            self._compiledExprByAxis.pop((plotIdx, axisKey), None)

    def _resolveAxisValue(
        self, plotIdx: int, axisKey: str, axisDef: Any
    ) -> float | None:
        if not isinstance(axisDef, dict):
            return None
        axisType = str(axisDef.get("type", ""))
        if axisType == "time":
            return self._elapsedSinceRunStart(self._latestTimestamp)
        if axisType == "var":
            instId = str(axisDef.get("instrumentId", ""))
            key = str(axisDef.get("key", ""))
            # Treat __time__:time as the runtime timestamp (independent variable),
            # not the configured sweep setpoint.
            if instId == "__time__" and key == "time":
                return self._elapsedSinceRunStart(self._latestTimestamp)
            valKey = (instId, key)
            return self._latestValues.get(valKey)
        if axisType == "expr":
            compiled = self._compiledExprByAxis.get((plotIdx, axisKey))
            if compiled is None:
                self._compileAxisExpression(plotIdx, axisKey, axisDef)
                compiled = self._compiledExprByAxis.get((plotIdx, axisKey))
            if compiled is None:
                return None
            try:
                return evaluateExpression(compiled, self._latestValues)
            except ExpressionError as exc:
                self._emitExpressionError(plotIdx, axisKey, str(exc))
                return None
        return None

    def _elapsedSinceRunStart(self, unixTimestamp: float) -> float:
        start = self._runStartUnixTimestamp
        if start is None:
            return float(unixTimestamp)
        return max(0.0, float(unixTimestamp) - float(start))

    def _getYSeriesDefs(self, plotDef: dict[str, Any]) -> list[dict[str, Any]]:
        ySeries = plotDef.get("ySeries", [])
        if isinstance(ySeries, list) and ySeries:
            return [d for d in ySeries if isinstance(d, dict)]
        yDef = plotDef.get("y", {})
        if isinstance(yDef, dict):
            return [yDef]
        return []

    def _seriesDisplayLabel(self, yDef: Any, yIdx: int) -> str:
        if isinstance(yDef, dict):
            name = str(yDef.get("name", "")).strip()
            # Backward-compat: treat legacy auto names like "Y1" as unnamed.
            if name and not re.fullmatch(r"Y\d+", name):
                return name
            if yDef.get("type") == "var":
                instId = str(yDef.get("instrumentId", "")).strip()
                key = str(yDef.get("key", "")).strip()
                if instId and key:
                    return f"{instId}:{key}"
            if yDef.get("type") == "expr":
                expr = str(yDef.get("expr", "")).strip()
                if expr:
                    return expr
        return f"Y{yIdx}"

    def _emitExpressionError(self, plotIdx: int, axisKey: str, msg: str) -> None:
        now = datetime.now().timestamp()
        key = (plotIdx, axisKey)
        last = self._lastExprErrorTimeByAxis.get(key, 0.0)
        if now - last < 1.0:
            return
        self._lastExprErrorTimeByAxis[key] = now
        self.statusLabel.setText(
            f"Plot {plotIdx + 1} {axisKey.upper()} expression: {msg}"
        )

    def _get2dSweepAxisRefs(
        self, jobDefinition: dict[str, Any]
    ) -> tuple[tuple[str, str], tuple[str, str]] | None:
        sweeps = jobDefinition.get("sweeps", [])
        if not isinstance(sweeps, list) or not sweeps:
            return None
        members = [s for s in sweeps if isinstance(s, dict)]
        if len(members) < 2:
            return None
        first = members[0]
        second = members[1]
        axisA = (str(first.get("instrumentId", "")), str(first.get("key", "")))
        axisB = (str(second.get("instrumentId", "")), str(second.get("key", "")))
        if axisA[0] and axisA[1] and axisB[0] and axisB[1]:
            return axisA, axisB
        return None

    def _normalizedHeatmapAxisDefs(
        self, plotDef: dict[str, Any], jobDefinition: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        xDefRaw = plotDef.get("x", {})
        yDefRaw = plotDef.get("heatmapY", {})

        def _asVarDef(raw: Any) -> dict[str, Any] | None:
            if not isinstance(raw, dict):
                return None
            if raw.get("type") == "var":
                inst = str(raw.get("instrumentId", ""))
                key = str(raw.get("key", ""))
                if inst and key:
                    return {"type": "var", "instrumentId": inst, "key": key}
            return None

        xVar = _asVarDef(xDefRaw)
        yVar = _asVarDef(yDefRaw)
        if xVar is not None and yVar is not None:
            return xVar, yVar

        sweepAxes = self._get2dSweepAxisRefs(jobDefinition)
        if sweepAxes is None:
            fallback = {"type": "var", "instrumentId": "", "key": ""}
            return xVar or fallback, yVar or fallback

        axisA = {
            "type": "var",
            "instrumentId": sweepAxes[0][0],
            "key": sweepAxes[0][1],
        }
        axisB = {
            "type": "var",
            "instrumentId": sweepAxes[1][0],
            "key": sweepAxes[1][1],
        }
        return xVar or axisA, yVar or axisB

    def _onSweepProgress(
        self,
        completedSweeps: int,
        totalSweeps: int,
        sweepPointIndex: int,
        sweepPointTotal: int,
        sweepLabel: str,
    ) -> None:
        if sweepPointIndex == 0:
            self._startSweepDataFile(sweepLabel)
        clampedPointTotal = max(1, sweepPointTotal)
        currentSweepFraction = min(max(sweepPointIndex / clampedPointTotal, 0.0), 1.0)

        # A job now has a single configured sweep (1D or 2D), so show only
        # point progress inside that sweep instead of "1/1 sweeps".
        self.sweepProgressBar.setValue(int(currentSweepFraction * 1000))
        if ":2d:" in sweepLabel and len(self._initializedSweeps) >= 2:
            outerTotal = max(1, int(self._initializedSweeps[0].get("points", 1)))
            innerTotal = max(1, int(self._initializedSweeps[1].get("points", 1)))
            if sweepPointIndex <= 0:
                outerIndex = 0
                innerIndex = 0
            else:
                point = min(sweepPointIndex, outerTotal * innerTotal)
                outerIndex = ((point - 1) // innerTotal) + 1
                innerIndex = ((point - 1) % innerTotal) + 1
            self.sweepProgressLabel.setText(
                f"Sweep Progress: Outer {outerIndex}/{outerTotal}, "
                f"Inner {innerIndex}/{innerTotal} ({sweepLabel})"
            )
        else:
            self.sweepProgressLabel.setText(
                f"Sweep Progress: Point {sweepPointIndex}/{sweepPointTotal} ({sweepLabel})"
            )

    def _selectDataExportTarget(
        self, jobDefinition: dict[str, Any]
    ) -> tuple[Path, str] | None:
        jobId = str(jobDefinition.get("jobId", "job")).strip() or "job"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safeJobId = "".join(c if c.isalnum() or c in "._-" else "_" for c in jobId)
        outDir = genesis_runs_dir()
        defaultPath = outDir / f"{safeJobId}_{stamp}.csv"
        pathStr, selectedFilter = QFileDialog.getSaveFileName(
            self,
            "Save Raw Data",
            str(defaultPath),
            filter="CSV files (*.csv);;NumPy files (*.npy)",
        )
        if not pathStr:
            return None
        path = Path(pathStr)
        exportFormat = "npy" if "npy" in selectedFilter.lower() else "csv"
        if exportFormat == "csv" and path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        if exportFormat == "npy" and path.suffix.lower() != ".npy":
            path = path.with_suffix(".npy")
        return path, exportFormat

    def _prepareDataExport(self, path: Path, exportFormat: str) -> None:
        self._closeDataLogFile()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._dataBasePath = path
        self._dataExportFormat = exportFormat
        self._dataColumnKeys = self._buildDataColumnKeys()
        self.statusLabel.setText(
            f"Raw export configured ({exportFormat.upper()}) at {path.parent}"
        )

    def _startSweepDataFile(self, sweepLabel: str) -> None:
        self._finalizeCurrentSweepFile()
        if self._dataBasePath is None:
            return
        self._currentSweepLabel = str(sweepLabel)
        labelSafe = (
            re.sub(r"[^A-Za-z0-9._-]+", "_", str(sweepLabel)).strip("_") or "sweep"
        )
        stem = self._dataBasePath.stem
        ext = ".npy" if self._dataExportFormat == "npy" else ".csv"
        fileName = f"{stem}_{labelSafe}{ext}"
        filePath = self._dataBasePath.with_name(fileName)
        self._currentSweepFilePath = filePath
        self._currentSweepRows = []
        if self._dataExportFormat == "csv":
            self._dataFilePath = filePath
            self._dataFileHandle = filePath.open("w", newline="", encoding="utf8")
            self._dataCsvWriter = csv.writer(self._dataFileHandle)
            header = ["timestamp"] + [
                f"{instrumentId}:{key}" for instrumentId, key in self._dataColumnKeys
            ]
            self._dataCsvWriter.writerow(header)
        self.statusLabel.setText(f"Logging raw data: {filePath.name}")

    def _buildDataColumnKeys(self) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        for instrumentId in sorted(self._rawLogKeysByInstrumentId.keys()):
            for key in sorted(self._rawLogKeysByInstrumentId.get(instrumentId, set())):
                # For time sweeps, the independent variable is represented by
                # timestamp; omit duplicate __time__:time export columns.
                if instrumentId == "__time__" and key == "time":
                    continue
                keys.append((instrumentId, key))
        return keys

    def _appendDataRow(
        self, timestamp: float, valuesByInstrumentId: dict[str, dict[str, float]]
    ) -> None:
        if self._dataBasePath is None:
            return
        row: dict[str, float] = {"timestamp": float(timestamp)}
        for instrumentId, key in self._dataColumnKeys:
            value = valuesByInstrumentId.get(instrumentId, {}).get(key, float("nan"))
            row[f"{instrumentId}:{key}"] = float(value)
        self._currentSweepRows.append(row)
        if self._dataExportFormat == "csv":
            if self._dataCsvWriter is None or self._dataFileHandle is None:
                return
            csvRow = [row["timestamp"]] + [
                row[f"{instrumentId}:{key}"]
                for instrumentId, key in self._dataColumnKeys
            ]
            self._dataCsvWriter.writerow(csvRow)
            self._dataFileHandle.flush()
        else:
            if len(self._currentSweepRows) % self._npyCheckpointEveryRows == 0:
                self._checkpointCurrentSweepFile()

    def _closeDataLogFile(self) -> None:
        self._finalizeCurrentSweepFile()
        if self._dataFileHandle is not None:
            try:
                self._dataFileHandle.close()
            except Exception:
                pass
        self._dataFileHandle = None
        self._dataCsvWriter = None
        self._dataFilePath = None
        self._dataBasePath = None
        self._currentSweepFilePath = None
        self._currentSweepRows = []
        self._currentSweepLabel = ""
        self._dataColumnKeys = []

    def _finalizeCurrentSweepFile(self) -> None:
        if self._currentSweepFilePath is None:
            return
        if self._dataExportFormat == "npy":
            self._checkpointCurrentSweepFile()
        if self._dataFileHandle is not None:
            try:
                self._dataFileHandle.close()
            except Exception:
                pass
        self._dataFileHandle = None
        self._dataCsvWriter = None
        self._currentSweepRows = []
        self._currentSweepFilePath = None

    def _checkpointCurrentSweepFile(self) -> None:
        if self._dataExportFormat != "npy":
            return
        if self._currentSweepFilePath is None:
            return
        rows = self._currentSweepRows
        payload = {
            "timestamp": np.asarray([r["timestamp"] for r in rows], dtype=float),
            "sweepLabel": np.asarray([self._currentSweepLabel], dtype=object),
            "columns": np.asarray(
                [f"{instrumentId}:{key}" for instrumentId, key in self._dataColumnKeys],
                dtype=object,
            ),
        }
        for instrumentId, key in self._dataColumnKeys:
            col = f"{instrumentId}:{key}"
            payload[col] = np.asarray(
                [r.get(col, float("nan")) for r in rows], dtype=float
            )
        tmpPath = self._currentSweepFilePath.with_suffix(
            self._currentSweepFilePath.suffix + ".tmp"
        )
        with tmpPath.open("wb") as handle:
            np.save(handle, payload, allow_pickle=True)
        tmpPath.replace(self._currentSweepFilePath)

    def _buildSweepValues(self, sweep: dict[str, Any]) -> np.ndarray:
        start = float(sweep.get("start", 0.0))
        stop = float(sweep.get("stop", 0.0))
        points = max(2, int(sweep.get("points", 2)))
        spacing = str(sweep.get("spacing", "linear"))

        if points == 1:
            return np.asarray([start], dtype=np.float64)

        if spacing == "log" and start > 0 and stop > 0:
            return np.logspace(
                np.log10(start), np.log10(stop), points, dtype=np.float64
            )

        return np.linspace(start, stop, points, dtype=np.float64)
