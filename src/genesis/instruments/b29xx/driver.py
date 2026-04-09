from __future__ import annotations

from typing import Any

from genesis.core.instrument.base_instrument import BaseInstrument
from genesis.core.instrument.config_field import ConfigChoice, ConfigFieldDefinition
from genesis.core.instrument.registry import InstrumentRegistry
from genesis.core.transport.base_transport import BaseTransport

INSTRUMENT_TYPE_KEY = "b29xx"


class B29xxInstrument(BaseInstrument):
    """
    Agilent/Keysight B29xx SMU driver (remote SCPI over VISA).

    Commands follow B2900A/B SCPI Command Reference.  Channel is
    selected via numeric suffix [c] (1 or 2):
    - :SOUR[c]:FUNC:MODE VOLT|CURR
    - :SOUR[c]:VOLT <value>, :SOUR[c]:CURR <value>
    - :SENS[c]:CURR:PROT <value>, :SENS[c]:VOLT:PROT <value>
    - :OUTP[c] ON|OFF
    - :MEAS:VOLT? (@c), :MEAS:CURR? (@c), :MEAS:RES? (@c)
    - Trigger sources: AINT, BUS, TIM, EXT1
    """

    displayName = "Agilent/Keysight B29xx SMU"

    @classmethod
    def getDefaultTransportKey(cls) -> str:
        return "visa"

    @classmethod
    def getSupportedTransportKeys(cls) -> list[str]:
        return ["visa"]

    @classmethod
    def getDefaultAddress(cls) -> str:
        # B2900 series factory-default GPIB address is 23.
        return "GPIB0::23::INSTR"

    @classmethod
    def getAvailableMeasurementSignals(cls) -> list[tuple[str, str]]:
        return [
            ("forceVoltageV", "Force Voltage"),
            ("forceCurrentA", "Force Current"),
            ("senseVoltageV", "Sense Voltage"),
            ("senseCurrentA", "Sense Current"),
            ("senseResistanceOhm", "Sense Resistance"),
        ]

    @classmethod
    def getJobConfigFields(cls) -> list[ConfigFieldDefinition]:
        return [
            ConfigFieldDefinition(
                key="channel",
                label="Channel",
                fieldType="enum",
                default=1,
                choices=[
                    ConfigChoice(1, "Channel 1"),
                    ConfigChoice(2, "Channel 2"),
                ],
                helpText="SMU channel selection for dual-channel models.",
            ),
            ConfigFieldDefinition(
                key="forceMode",
                label="Force Mode",
                fieldType="enum",
                default="VOLT",
                choices=[
                    ConfigChoice("VOLT", "Force Voltage / Measure Current"),
                    ConfigChoice("CURR", "Force Current / Measure Voltage"),
                ],
                helpText="Maps to :SOUR:FUNC:MODE VOLT|CURR.",
            ),
            ConfigFieldDefinition(
                key="forceVoltageLevelV",
                label="Force Voltage Level (V)",
                fieldType="float",
                default=0.0,
                minValue=-210.0,
                maxValue=210.0,
                stepValue=0.001,
                sweepable=True,
                helpText="Used when Force Mode is VOLT (:SOUR:VOLT).",
            ),
            ConfigFieldDefinition(
                key="forceCurrentLevelA",
                label="Force Current Level (A)",
                fieldType="float",
                default=100e-6,
                minValue=-3.0,
                maxValue=3.0,
                stepValue=1e-6,
                sweepable=True,
                helpText="Used when Force Mode is CURR (:SOUR:CURR).",
            ),
            ConfigFieldDefinition(
                key="currentComplianceA",
                label="Current Compliance (A)",
                fieldType="float",
                default=100e-6,
                minValue=0.0,
                maxValue=3.0,
                stepValue=1e-6,
                helpText="Compliance in voltage-force mode (:SENS:CURR:PROT).",
            ),
            ConfigFieldDefinition(
                key="voltageComplianceV",
                label="Voltage Compliance (V)",
                fieldType="float",
                default=2.0,
                minValue=0.0,
                maxValue=210.0,
                stepValue=0.001,
                helpText="Compliance in current-force mode (:SENS:VOLT:PROT).",
            ),
            ConfigFieldDefinition(
                key="outputEnabled",
                label="Output Enabled",
                fieldType="enum",
                default=0,
                choices=[ConfigChoice(1, "On"), ConfigChoice(0, "Off")],
                helpText="Output state (:OUTP ON|OFF).",
            ),
            ConfigFieldDefinition(
                key="voltageNplc",
                label="Voltage NPLC",
                fieldType="float",
                default=0.1,
                minValue=0.001,
                maxValue=10.0,
                stepValue=0.001,
                helpText="Voltage integration time in power line cycles (:SENS:VOLT:NPLC).",
            ),
            ConfigFieldDefinition(
                key="currentNplc",
                label="Current NPLC",
                fieldType="float",
                default=0.1,
                minValue=0.001,
                maxValue=10.0,
                stepValue=0.001,
                helpText="Current integration time in power line cycles (:SENS:CURR:NPLC).",
            ),
            ConfigFieldDefinition(
                key="voltageRangeAuto",
                label="Voltage Range Auto",
                fieldType="enum",
                default=1,
                choices=[ConfigChoice(1, "On"), ConfigChoice(0, "Off")],
                helpText="Voltage measurement auto range (:SENS:VOLT:RANG:AUTO).",
            ),
            ConfigFieldDefinition(
                key="currentRangeAuto",
                label="Current Range Auto",
                fieldType="enum",
                default=1,
                choices=[ConfigChoice(1, "On"), ConfigChoice(0, "Off")],
                helpText="Current measurement auto range (:SENS:CURR:RANG:AUTO).",
            ),
            ConfigFieldDefinition(
                key="voltageSenseRangeV",
                label="Voltage Sense Range (V)",
                fieldType="float",
                default=2.0,
                minValue=0.0,
                maxValue=210.0,
                stepValue=0.001,
                helpText="Manual voltage measurement range (:SENS:VOLT:RANG) when auto range is Off.",
            ),
            ConfigFieldDefinition(
                key="currentSenseRangeA",
                label="Current Sense Range (A)",
                fieldType="float",
                default=100e-6,
                minValue=0.0,
                maxValue=3.0,
                stepValue=1e-6,
                helpText="Manual current measurement range (:SENS:CURR:RANG) when auto range is Off.",
            ),
            ConfigFieldDefinition(
                key="triggerAcquireSource",
                label="Trigger Acquire Source",
                fieldType="enum",
                default="AINT",
                choices=[
                    ConfigChoice("AINT", "Auto Internal"),
                    ConfigChoice("BUS", "Bus (*TRG)"),
                    ConfigChoice("EXT1", "External 1"),
                    ConfigChoice("TIM", "Timer"),
                ],
                helpText="Acquisition trigger source (:TRIG:ACQ:SOUR).",
            ),
            ConfigFieldDefinition(
                key="triggerAcquireDelayS",
                label="Trigger Acquire Delay (s)",
                fieldType="float",
                default=0.0,
                minValue=0.0,
                maxValue=100000.0,
                stepValue=0.001,
                helpText="Acquisition trigger delay (:TRIG:ACQ:DEL).",
            ),
            ConfigFieldDefinition(
                key="triggerAcquireDelayAuto",
                label="Trigger Acquire Delay Auto",
                fieldType="enum",
                default=1,
                choices=[ConfigChoice(1, "On"), ConfigChoice(0, "Off")],
                helpText="Automatic acquisition trigger delay (:TRIG:ACQ:DEL:AUTO).",
            ),
            ConfigFieldDefinition(
                key="triggerAcquireCount",
                label="Trigger Acquire Count",
                fieldType="int",
                default=1,
                minValue=1,
                maxValue=100000,
                stepValue=1,
                helpText="Acquisition trigger count (:TRIG:ACQ:COUN).",
            ),
            ConfigFieldDefinition(
                key="triggerAcquireTimerS",
                label="Trigger Acquire Timer (s)",
                fieldType="float",
                default=0.1,
                minValue=1e-6,
                maxValue=100000.0,
                stepValue=0.001,
                helpText="Timer interval when acquire source is TIM (:TRIG:ACQ:TIM).",
            ),
            ConfigFieldDefinition(
                key="triggerTransientSource",
                label="Trigger Transient Source",
                fieldType="enum",
                default="AINT",
                choices=[
                    ConfigChoice("AINT", "Auto Internal"),
                    ConfigChoice("BUS", "Bus (*TRG)"),
                    ConfigChoice("EXT1", "External 1"),
                    ConfigChoice("TIM", "Timer"),
                ],
                helpText="Transient/source trigger source (:TRIG:TRAN:SOUR).",
            ),
            ConfigFieldDefinition(
                key="triggerTransientDelayS",
                label="Trigger Transient Delay (s)",
                fieldType="float",
                default=0.0,
                minValue=0.0,
                maxValue=100000.0,
                stepValue=0.001,
                helpText="Transient/source trigger delay (:TRIG:TRAN:DEL).",
            ),
            ConfigFieldDefinition(
                key="triggerTransientDelayAuto",
                label="Trigger Transient Delay Auto",
                fieldType="enum",
                default=1,
                choices=[ConfigChoice(1, "On"), ConfigChoice(0, "Off")],
                helpText="Automatic transient/source trigger delay (:TRIG:TRAN:DEL:AUTO).",
            ),
            ConfigFieldDefinition(
                key="triggerTransientCount",
                label="Trigger Transient Count",
                fieldType="int",
                default=1,
                minValue=1,
                maxValue=100000,
                stepValue=1,
                helpText="Transient/source trigger count (:TRIG:TRAN:COUN).",
            ),
            ConfigFieldDefinition(
                key="triggerTransientTimerS",
                label="Trigger Transient Timer (s)",
                fieldType="float",
                default=0.1,
                minValue=1e-6,
                maxValue=100000.0,
                stepValue=0.001,
                helpText="Timer interval when transient source is TIM (:TRIG:TRAN:TIM).",
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
        # Do not send full-reset commands here; apply only configured values.
        for key, value in self.jobConfig.items():
            self.applyConfigValue(str(key), value)

    def applySafeState(self) -> None:
        target = self._safeConfig or self.jobConfig
        for key, value in target.items():
            self.applyConfigValue(str(key), value)

    def readMeasurements(self, signalKeys: list[str]) -> dict[str, float]:
        ch = int(self.jobConfig.get("channel", 1))
        values: dict[str, float] = {}
        for key in signalKeys:
            if key == "senseVoltageV":
                values[key] = self._queryFloat(f":MEAS:VOLT? (@{ch})")
            elif key == "senseCurrentA":
                values[key] = self._queryFloat(f":MEAS:CURR? (@{ch})")
            elif key == "senseResistanceOhm":
                values[key] = self._queryFloat(f":MEAS:RES? (@{ch})")
            elif key == "forceVoltageV":
                values[key] = float(self.jobConfig.get("forceVoltageLevelV", 0.0))
            elif key == "forceCurrentA":
                values[key] = float(self.jobConfig.get("forceCurrentLevelA", 0.0))
        return values

    def applyConfigValue(self, key: str, value: float | int | str) -> None:
        self.jobConfig[key] = value
        mode = str(self.jobConfig.get("forceMode", "VOLT")).upper()

        ch = int(self.jobConfig.get("channel", 1))

        if key == "channel":
            return

        if key == "forceMode":
            mode = str(value).upper()
            if mode not in {"VOLT", "CURR"}:
                raise ValueError(f"Unsupported force mode: {value!r}")
            self.transport.write(f":SOUR{ch}:FUNC:MODE {mode}")
            return

        if key == "forceVoltageLevelV":
            if mode != "VOLT":
                return
            self.transport.write(f":SOUR{ch}:VOLT {self._fmtFloat(value)}")
            return

        if key == "forceCurrentLevelA":
            if mode != "CURR":
                return
            self.transport.write(f":SOUR{ch}:CURR {self._fmtFloat(value)}")
            return

        if key == "currentComplianceA":
            self.transport.write(f":SENS{ch}:CURR:PROT {self._fmtFloat(value)}")
            return

        if key == "voltageComplianceV":
            self.transport.write(f":SENS{ch}:VOLT:PROT {self._fmtFloat(value)}")
            return

        if key == "outputEnabled":
            enabled = int(value) != 0
            self.transport.write(f":OUTP{ch} ON" if enabled else f":OUTP{ch} OFF")
            return

        if key == "voltageNplc":
            self.transport.write(f":SENS{ch}:VOLT:NPLC {self._fmtFloat(value)}")
            return

        if key == "currentNplc":
            self.transport.write(f":SENS{ch}:CURR:NPLC {self._fmtFloat(value)}")
            return

        if key == "voltageRangeAuto":
            enabled = int(value) != 0
            self.transport.write(
                f":SENS{ch}:VOLT:RANG:AUTO ON"
                if enabled
                else f":SENS{ch}:VOLT:RANG:AUTO OFF"
            )
            if not enabled:
                manual = self.jobConfig.get("voltageSenseRangeV")
                if manual is not None:
                    self.transport.write(
                        f":SENS{ch}:VOLT:RANG {self._fmtFloat(manual)}"
                    )
            return

        if key == "currentRangeAuto":
            enabled = int(value) != 0
            self.transport.write(
                f":SENS{ch}:CURR:RANG:AUTO ON"
                if enabled
                else f":SENS{ch}:CURR:RANG:AUTO OFF"
            )
            if not enabled:
                manual = self.jobConfig.get("currentSenseRangeA")
                if manual is not None:
                    self.transport.write(
                        f":SENS{ch}:CURR:RANG {self._fmtFloat(manual)}"
                    )
            return

        if key == "voltageSenseRangeV":
            if int(self.jobConfig.get("voltageRangeAuto", 1)) != 0:
                return
            self.transport.write(f":SENS{ch}:VOLT:RANG {self._fmtFloat(value)}")
            return

        if key == "currentSenseRangeA":
            if int(self.jobConfig.get("currentRangeAuto", 1)) != 0:
                return
            self.transport.write(f":SENS{ch}:CURR:RANG {self._fmtFloat(value)}")
            return

        if key == "triggerAcquireSource":
            source = str(value).upper()
            if source == "IMM":
                source = "AINT"
            if source == "EXT":
                source = "EXT1"
            if source not in {"AINT", "BUS", "EXT1", "TIM"}:
                raise ValueError(f"Unsupported acquire trigger source: {value!r}")
            self.transport.write(f":TRIG:ACQ:SOUR {source}")
            if source == "TIM":
                timer = self.jobConfig.get("triggerAcquireTimerS")
                if timer is not None:
                    self.transport.write(f":TRIG:ACQ:TIM {self._fmtFloat(timer)}")
            return

        if key == "triggerAcquireDelayS":
            if int(self.jobConfig.get("triggerAcquireDelayAuto", 1)) != 0:
                return
            self.transport.write(f":TRIG:ACQ:DEL {self._fmtFloat(value)}")
            return

        if key == "triggerAcquireDelayAuto":
            enabled = int(value) != 0
            self.transport.write(
                ":TRIG:ACQ:DEL:AUTO ON" if enabled else ":TRIG:ACQ:DEL:AUTO OFF"
            )
            if not enabled:
                delay = self.jobConfig.get("triggerAcquireDelayS")
                if delay is not None:
                    self.transport.write(f":TRIG:ACQ:DEL {self._fmtFloat(delay)}")
            return

        if key == "triggerAcquireCount":
            self.transport.write(f":TRIG:ACQ:COUN {int(value)}")
            return

        if key == "triggerAcquireTimerS":
            if str(self.jobConfig.get("triggerAcquireSource", "AINT")).upper() != "TIM":
                return
            self.transport.write(f":TRIG:ACQ:TIM {self._fmtFloat(value)}")
            return

        if key == "triggerTransientSource":
            source = str(value).upper()
            if source == "IMM":
                source = "AINT"
            if source == "EXT":
                source = "EXT1"
            if source not in {"AINT", "BUS", "EXT1", "TIM"}:
                raise ValueError(f"Unsupported transient trigger source: {value!r}")
            self.transport.write(f":TRIG:TRAN:SOUR {source}")
            if source == "TIM":
                timer = self.jobConfig.get("triggerTransientTimerS")
                if timer is not None:
                    self.transport.write(f":TRIG:TRAN:TIM {self._fmtFloat(timer)}")
            return

        if key == "triggerTransientDelayS":
            if int(self.jobConfig.get("triggerTransientDelayAuto", 1)) != 0:
                return
            self.transport.write(f":TRIG:TRAN:DEL {self._fmtFloat(value)}")
            return

        if key == "triggerTransientDelayAuto":
            enabled = int(value) != 0
            self.transport.write(
                ":TRIG:TRAN:DEL:AUTO ON" if enabled else ":TRIG:TRAN:DEL:AUTO OFF"
            )
            if not enabled:
                delay = self.jobConfig.get("triggerTransientDelayS")
                if delay is not None:
                    self.transport.write(f":TRIG:TRAN:DEL {self._fmtFloat(delay)}")
            return

        if key == "triggerTransientCount":
            self.transport.write(f":TRIG:TRAN:COUN {int(value)}")
            return

        if key == "triggerTransientTimerS":
            if (
                str(self.jobConfig.get("triggerTransientSource", "AINT")).upper()
                != "TIM"
            ):
                return
            self.transport.write(f":TRIG:TRAN:TIM {self._fmtFloat(value)}")
            return

    def _queryFloat(self, command: str) -> float:
        response = self.transport.query(command).strip()
        # Handle comma-separated response forms by taking the first numeric field.
        if "," in response:
            response = response.split(",")[0].strip()
        return float(response)

    def _fmtFloat(self, value: float | int | str) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        return f"{float(value):.12g}"


def _b29xxFactory(
    name: str,
    transport: BaseTransport,
    metadata: dict[str, Any] | None = None,
    jobConfig: dict[str, Any] | None = None,
) -> BaseInstrument:
    return B29xxInstrument(
        name=name,
        transport=transport,
        metadata=metadata,
        jobConfig=jobConfig,
    )


def registerInstruments(registry: InstrumentRegistry) -> None:
    registry.registerInstrument(
        key=INSTRUMENT_TYPE_KEY,
        instrumentType=B29xxInstrument,
        factory=_b29xxFactory,
    )
