from __future__ import annotations

import time
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from genesis.core.instrument.base_instrument import BaseInstrument


class AcquisitionSample(dict):
    pass


class AcquisitionWorker(QObject):
    sampleEmitted = Signal(str, float, dict)  # instrumentId, timestamp, values
    statusMessage = Signal(str)
    sweepProgress = Signal(int, int, int, int, str)

    def __init__(
        self,
        instrumentsById: dict[str, BaseInstrument],
        measurementKeysByInstrumentId: dict[str, list[str]],
        sweeps: list[dict[str, Any]] | None = None,
        intervalSeconds: float = 0.2,
    ) -> None:
        super().__init__()
        self.instrumentsById = instrumentsById
        self.measurementKeysByInstrumentId = measurementKeysByInstrumentId
        self.sweeps = sweeps or []
        self.intervalSeconds = intervalSeconds
        self._shouldStop = False
        self._activeSweepValuesByInstrumentId: dict[str, dict[str, float]] = {}

    def requestStop(self) -> None:
        self._shouldStop = True

    def run(self) -> None:
        self.statusMessage.emit("Acquisition started.")
        if self.sweeps:
            self._runSweepSuites()
        else:
            while not self._shouldStop:
                self._sampleAllInstruments(time.time())
                time.sleep(self.intervalSeconds)
        self.statusMessage.emit("Acquisition stopped.")

    def _runSweepSuites(self) -> None:
        suites = self._buildSweepSuites(self.sweeps)
        totalSuites = len(suites)
        for suiteIndex, suiteSweeps in enumerate(suites):
            if self._shouldStop:
                break
            completedBefore = suiteIndex
            if len(suiteSweeps) == 1:
                self._runSingleSweep(
                    suiteSweeps[0],
                    suiteOrdinal=suiteIndex + 1,
                    completedBefore=completedBefore,
                    totalSuites=totalSuites,
                )
            elif len(suiteSweeps) == 2:
                self._runNestedSweep2d(
                    suiteSweeps[0],
                    suiteSweeps[1],
                    suiteOrdinal=suiteIndex + 1,
                    completedBefore=completedBefore,
                    totalSuites=totalSuites,
                )
            else:
                self.statusMessage.emit(
                    f"Skipping suite {suiteIndex + 1}: nested depth {len(suiteSweeps)} is unsupported."
                )

    def _runSingleSweep(
        self,
        sweep: dict[str, Any],
        suiteOrdinal: int,
        completedBefore: int,
        totalSuites: int,
    ) -> None:
        instrumentId = str(sweep.get("instrumentId", ""))
        key = str(sweep.get("key", ""))
        if not instrumentId or not key:
            return
        isTimeSweep = instrumentId == "__time__" and key == "time"
        instrument = self.instrumentsById.get(instrumentId)
        if not isTimeSweep and instrument is None:
            self.statusMessage.emit(
                f"Skipping sweep {instrumentId}:{key} (instrument not found)."
            )
            return

        values = self._buildSweepValues(sweep)
        settle = float(sweep.get("settleTimeSeconds", 0.0))
        label = f"suite{suiteOrdinal}:{instrumentId}:{key}"
        self.statusMessage.emit(
            f"Running suite {suiteOrdinal} sweep {instrumentId}:{key} ({len(values)} points)."
        )
        self.sweepProgress.emit(completedBefore, totalSuites, 0, len(values), label)

        sweepStart = time.time()
        for pointIndex, point in enumerate(values, start=1):
            if self._shouldStop:
                break
            if isTimeSweep:
                target = sweepStart + float(point)
                self._sleepUntilOrStop(target)
            else:
                try:
                    instrument.applyConfigValue(key, point)
                except Exception as exc:
                    self.statusMessage.emit(f"{instrumentId}:{key} set failed: {exc}")
                    continue

            self._activeSweepValuesByInstrumentId.setdefault(instrumentId, {})[
                key
            ] = point
            self._sleepWithStop(settle)
            if self._shouldStop:
                break
            self._sampleAllInstruments(time.time())
            self.sweepProgress.emit(
                completedBefore + 1, totalSuites, pointIndex, len(values), label
            )

    def _runNestedSweep2d(
        self,
        outerSweep: dict[str, Any],
        innerSweep: dict[str, Any],
        suiteOrdinal: int,
        completedBefore: int,
        totalSuites: int,
    ) -> None:
        outerInstId = str(outerSweep.get("instrumentId", ""))
        outerKey = str(outerSweep.get("key", ""))
        innerInstId = str(innerSweep.get("instrumentId", ""))
        innerKey = str(innerSweep.get("key", ""))
        if not outerInstId or not outerKey or not innerInstId or not innerKey:
            return

        outerIsTime = outerInstId == "__time__" and outerKey == "time"
        innerIsTime = innerInstId == "__time__" and innerKey == "time"
        outerInstrument = self.instrumentsById.get(outerInstId)
        innerInstrument = self.instrumentsById.get(innerInstId)
        if not outerIsTime and outerInstrument is None:
            self.statusMessage.emit(
                f"Skipping 2D sweep {outerInstId}:{outerKey} (instrument not found)."
            )
            return
        if not innerIsTime and innerInstrument is None:
            self.statusMessage.emit(
                f"Skipping 2D sweep {innerInstId}:{innerKey} (instrument not found)."
            )
            return

        outerValues = self._buildSweepValues(outerSweep)
        innerValues = self._buildSweepValues(innerSweep)
        outerSettle = float(outerSweep.get("settleTimeSeconds", 0.0))
        innerSettle = float(innerSweep.get("settleTimeSeconds", 0.0))
        totalPoints = len(outerValues) * len(innerValues)
        label = (
            f"suite{suiteOrdinal}:2d:{outerInstId}:{outerKey}|{innerInstId}:{innerKey}"
        )
        self.statusMessage.emit(
            f"Running suite {suiteOrdinal} 2D sweep {outerInstId}:{outerKey} x {innerInstId}:{innerKey} ({totalPoints} points)."
        )
        self.sweepProgress.emit(completedBefore, totalSuites, 0, totalPoints, label)

        sweepStart = time.time()
        pointIndex = 0
        for outerValue in outerValues:
            if self._shouldStop:
                break
            if outerIsTime:
                outerTarget = sweepStart + float(outerValue)
                self._sleepUntilOrStop(outerTarget)
            else:
                try:
                    outerInstrument.applyConfigValue(outerKey, outerValue)
                except Exception as exc:
                    self.statusMessage.emit(
                        f"{outerInstId}:{outerKey} set failed: {exc}"
                    )
                    continue
            self._activeSweepValuesByInstrumentId.setdefault(outerInstId, {})[
                outerKey
            ] = float(outerValue)
            self._sleepWithStop(outerSettle)
            if self._shouldStop:
                break

            innerSweepStart = time.time()
            for innerValue in innerValues:
                if self._shouldStop:
                    break
                if innerIsTime:
                    innerTarget = innerSweepStart + float(innerValue)
                    self._sleepUntilOrStop(innerTarget)
                else:
                    try:
                        innerInstrument.applyConfigValue(innerKey, innerValue)
                    except Exception as exc:
                        self.statusMessage.emit(
                            f"{innerInstId}:{innerKey} set failed: {exc}"
                        )
                        continue

                self._activeSweepValuesByInstrumentId.setdefault(innerInstId, {})[
                    innerKey
                ] = float(innerValue)
                self._sleepWithStop(innerSettle)
                if self._shouldStop:
                    break
                self._sampleAllInstruments(time.time())
                pointIndex += 1
                self.sweepProgress.emit(
                    completedBefore + 1, totalSuites, pointIndex, totalPoints, label
                )

    def _buildSweepSuites(
        self, sweeps: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        suitesById: dict[int, list[dict[str, Any]]] = {}
        orderedSuiteIds: list[int] = []
        nextImplicit = 1
        for sweep in sweeps:
            rawSuite = sweep.get("suiteIndex")
            if rawSuite is None:
                suiteId = nextImplicit
                nextImplicit += 1
            else:
                try:
                    suiteId = max(1, int(rawSuite))
                except Exception:
                    suiteId = nextImplicit
                    nextImplicit += 1
            if suiteId not in suitesById:
                suitesById[suiteId] = []
                orderedSuiteIds.append(suiteId)
            suitesById[suiteId].append(sweep)
        return [suitesById[suiteId] for suiteId in orderedSuiteIds]

    def _sampleAllInstruments(self, timestamp: float) -> None:
        for instrumentId, instrument in self.instrumentsById.items():
            keys = self.measurementKeysByInstrumentId.get(instrumentId, [])
            values: dict[str, float] = {}
            if keys:
                try:
                    values = instrument.readMeasurements(keys)
                except Exception as exc:
                    self.statusMessage.emit(f"{instrumentId}: read failed: {exc}")
                    values = {}

            # Include active sweep value(s) so these can be plotted/logged.
            activeSweep = self._activeSweepValuesByInstrumentId.get(instrumentId, {})
            for key, val in activeSweep.items():
                values[key] = float(val)

            self.sampleEmitted.emit(instrumentId, timestamp, values)
        activeTimeSweep = self._activeSweepValuesByInstrumentId.get("__time__", {})
        if "time" in activeTimeSweep:
            self.sampleEmitted.emit(
                "__time__", timestamp, {"time": float(activeTimeSweep["time"])}
            )

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

    def _sleepWithStop(self, seconds: float) -> None:
        if seconds <= 0:
            return
        end = time.time() + seconds
        while not self._shouldStop and time.time() < end:
            time.sleep(min(0.05, end - time.time()))

    def _sleepUntilOrStop(self, targetTime: float) -> None:
        while not self._shouldStop and time.time() < targetTime:
            time.sleep(min(0.05, targetTime - time.time()))


def startAcquisitionThread(
    worker: AcquisitionWorker,
) -> tuple[QThread, AcquisitionWorker]:
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    return thread, worker
