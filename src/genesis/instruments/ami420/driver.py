from __future__ import annotations

import time
from typing import Any, Callable

from genesis.core.instrument.base_instrument import BaseInstrument
from genesis.core.instrument.config_field import ConfigFieldDefinition
from genesis.core.instrument.registry import InstrumentRegistry
from genesis.core.transport.base_transport import BaseTransport

INSTRUMENT_TYPE_KEY = "ami420"


# STATE? response codes per Model 420 manual Table 4-5.
_STATE_RAMPING = 1
_STATE_HOLDING = 2
_STATE_PAUSED = 3
_STATE_MANUAL_UP = 4
_STATE_MANUAL_DOWN = 5
_STATE_ZEROING = 6
_STATE_QUENCH = 7
_STATE_HEATING_PSWITCH = 8
_STATE_AT_ZERO = 9


class Ami420Instrument(BaseInstrument):
    """
    American Magnetics Inc. Model 420 superconducting magnet power supply
    programmer (remote SCPI over GPIB/serial).

    Scope (per project requirements):
      - The only user-controllable, sweepable parameter exposed by this
        driver is the magnetic field setpoint (Tesla).
      - Ramp rates, programmed current values, and voltage limits are NOT
        configurable from Genesis. They remain managed on the controller.
      - Measurements expose the current magnet field, current, and voltage.
      - After commanding a new field setpoint, the driver waits
        asynchronously (cooperatively, on the acquisition thread) for the
        controller's internal ramp to bring the magnet within tolerance of
        the requested setpoint. The UI stays responsive and abort is honored
        between polls.

    Commands used (Model 420 SCPI, abbreviated headers per IEEE 488.2):
      - CONF:FIELD:UNITS 1          (force Tesla)
      - CONF:FIELD:PROG <value>     (set programmed field)
      - RAMP                          (start ramp to programmed field)
      - PAUSE                         (pause ramp on safe-state entry)
      - FIELD:MAG?                    (read measured field in Tesla)
      - CURR:MAG?                     (read magnet current in A)
      - VOLT:MAG?                     (read magnet voltage in V)
      - STATE?                        (ramping state per Table 4-5)
    """

    displayName = "AMI Model 420 Magnet Power Supply Programmer"

    @classmethod
    def getDefaultTransportKey(cls) -> str:
        return "visa"

    @classmethod
    def getSupportedTransportKeys(cls) -> list[str]:
        return ["visa"]

    @classmethod
    def getDefaultAddress(cls) -> str:
        # Model 420 factory-default IEEE-488 primary address is 22.
        return "GPIB0::22::INSTR"

    @classmethod
    def getAvailableMeasurementSignals(cls) -> list[tuple[str, str]]:
        return [
            ("magnetFieldT", "Magnet Field (T)"),
            ("magnetCurrentA", "Magnet Current (A)"),
            ("magnetVoltageV", "Magnet Voltage (V)"),
        ]

    @classmethod
    def getJobConfigFields(cls) -> list[ConfigFieldDefinition]:
        # NOTE: Intentionally minimal. The user has explicitly requested that
        # ramp rates, current setpoints, and voltage limits not be exposed in
        # this UI; those remain configured on the controller itself.
        return [
            ConfigFieldDefinition(
                key="targetFieldT",
                label="Target Field (T)",
                fieldType="float",
                default=0.0,
                # Conservative software-side bounds; the Model 420 has its
                # own current limit enforced internally based on the coil
                # constant and magnet rating.
                minValue=-30.0,
                maxValue=30.0,
                stepValue=0.001,
                sweepable=True,
                helpText=(
                    "Programmed magnetic field setpoint in Tesla. Writing this "
                    "value issues CONF:FIELD:PROG <value> followed by "
                    "RAMP, then waits asynchronously for the controller's "
                    "internal ramp to bring the measured field within "
                    "setpointToleranceT of the target."
                ),
            ),
            ConfigFieldDefinition(
                key="setpointToleranceT",
                label="Setpoint Tolerance (T)",
                fieldType="float",
                default=0.001,
                minValue=0.0,
                maxValue=10.0,
                stepValue=0.0001,
                helpText=(
                    "Absolute tolerance applied to |measured - target| when "
                    "deciding the controller has finished ramping. Software "
                    "only; not sent to the instrument."
                ),
            ),
            ConfigFieldDefinition(
                key="setpointTimeoutSeconds",
                label="Setpoint Timeout (s)",
                fieldType="float",
                default=1800.0,
                minValue=0.0,
                maxValue=24.0 * 3600.0,
                stepValue=1.0,
                helpText=(
                    "Maximum time to wait for the controller to reach the "
                    "commanded field before reporting a settling failure. "
                    "Zero disables the timeout."
                ),
            ),
            ConfigFieldDefinition(
                key="setpointPollIntervalSeconds",
                label="Poll Interval (s)",
                fieldType="float",
                default=0.5,
                minValue=0.05,
                maxValue=10.0,
                stepValue=0.05,
                helpText=(
                    "How often the driver re-queries FIELD:MAG? and STATE? "
                    "while waiting for the ramp to complete."
                ),
            ),
        ]

    def __init__(
        self,
        name: str,
        transport: BaseTransport,
        metadata: dict[str, Any] | None = None,
        jobConfig: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name=name, transport=transport, metadata=metadata)
        self.jobConfig = dict(self.getDefaultJobConfig())
        self.jobConfig.update(jobConfig or {})
        self._safeConfig = dict((metadata or {}).get("safeConfig", {}))

    def initialize(self) -> None:
        # Force field units to Tesla so all numeric values are interpreted
        # consistently regardless of the front-panel setting. We deliberately
        # do not touch ramp rate, current limit, or voltage limit here.
        self.transport.write("CONF:FIELD:UNITS 1")
        # Apply any user-set field setpoint via the normal sweep code path.
        target = self.jobConfig.get("targetFieldT")
        if target is not None:
            self.applyConfigValue("targetFieldT", target)

    def applySafeState(self) -> None:
        # On safe-state entry the magnet is driven back toward 0 T using the
        # controller's own configured ramp rate. We never bypass that ramp.
        safeTarget = float(self._safeConfig.get("targetFieldT", 0.0))
        self.transport.write("CONF:FIELD:UNITS 1")
        self.transport.write(f"CONF:FIELD:PROG {self._fmtFloat(safeTarget)}")
        self.transport.write("RAMP")
        self.jobConfig["targetFieldT"] = safeTarget

    def readMeasurements(self, signalKeys: list[str]) -> dict[str, float]:
        values: dict[str, float] = {}
        for key in signalKeys:
            try:
                if key == "magnetFieldT":
                    values[key] = self._queryFloat("FIELD:MAG?")
                elif key == "magnetCurrentA":
                    values[key] = self._queryFloat("CURR:MAG?")
                elif key == "magnetVoltageV":
                    values[key] = self._queryFloat("VOLT:MAG?")
            except (ValueError, OSError):
                # Skip unreadable signals; runtime status surfaces this.
                continue
        return values

    def applyConfigValue(self, key: str, value: float | int | str) -> None:
        self.jobConfig[key] = value
        if key == "targetFieldT":
            self.transport.write(f"CONF:FIELD:PROG {self._fmtFloat(float(value))}")
            self.transport.write("RAMP")
            return
        # Tolerance, timeout, and poll interval are software-only knobs.
        if key in {
            "setpointToleranceT",
            "setpointTimeoutSeconds",
            "setpointPollIntervalSeconds",
        }:
            return

    def waitForSetpoint(
        self,
        key: str,
        target_value: float,
        should_stop: Callable[[], bool] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> bool:
        # Only the magnet field setpoint requires asynchronous settling. All
        # other config keys complete synchronously when written.
        if key != "targetFieldT":
            return True

        target = float(target_value)
        tolerance = max(0.0, float(self.jobConfig.get("setpointToleranceT", 0.001)))
        timeoutSeconds = float(self.jobConfig.get("setpointTimeoutSeconds", 0.0))
        pollInterval = max(
            0.05, float(self.jobConfig.get("setpointPollIntervalSeconds", 0.5))
        )

        startTime = time.time()
        while True:
            if should_stop is not None and should_stop():
                return False

            try:
                measured = self._queryFloat("FIELD:MAG?")
            except (ValueError, OSError):
                measured = float("nan")

            if on_progress is not None and measured == measured:
                on_progress(float(measured))

            try:
                stateValue = int(float(self._queryFloat("STATE?")))
            except (ValueError, OSError):
                stateValue = -1

            if stateValue == _STATE_QUENCH:
                # Fatal device condition: do not pretend we reached setpoint.
                return False

            if measured == measured and abs(measured - target) <= tolerance:
                if stateValue in (
                    _STATE_HOLDING,
                    _STATE_AT_ZERO,
                    _STATE_PAUSED,
                ):
                    return True

            if timeoutSeconds > 0.0 and (time.time() - startTime) >= timeoutSeconds:
                return False

            # Cooperative sleep: chunk into short slices so abort latency stays
            # bounded even with long poll intervals.
            remaining = pollInterval
            while remaining > 0.0:
                if should_stop is not None and should_stop():
                    return False
                chunk = min(0.05, remaining)
                time.sleep(chunk)
                remaining -= chunk

    def finalizeInitialization(
        self, should_stop: Callable[[], bool] | None = None
    ) -> bool:
        """
        After safe/config values are applied, wait until the Model 420 reports
        the magnet at the commanded field (controller-managed ramp complete).
        """
        raw = self.jobConfig.get("targetFieldT")
        if raw is None:
            return True
        return self.waitForSetpoint(
            "targetFieldT",
            float(raw),
            should_stop=should_stop,
            on_progress=None,
        )

    def _queryFloat(self, command: str) -> float:
        response = self.transport.query(command).strip()
        if "," in response:
            response = response.split(",")[0].strip()
        return float(response)

    def _fmtFloat(self, value: float | int | str) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        return f"{float(value):.12g}"


def _ami420Factory(
    name: str,
    transport: BaseTransport,
    metadata: dict[str, Any] | None = None,
    jobConfig: dict[str, Any] | None = None,
) -> BaseInstrument:
    return Ami420Instrument(
        name=name,
        transport=transport,
        metadata=metadata,
        jobConfig=jobConfig,
    )


def registerInstruments(registry: InstrumentRegistry) -> None:
    registry.registerInstrument(
        key=INSTRUMENT_TYPE_KEY,
        instrumentType=Ami420Instrument,
        factory=_ami420Factory,
    )
