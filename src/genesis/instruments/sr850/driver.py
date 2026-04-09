from __future__ import annotations

from typing import Any

from genesis.core.instrument.base_instrument import BaseInstrument
from genesis.core.instrument.config_field import ConfigChoice, ConfigFieldDefinition
from genesis.core.instrument.registry import InstrumentRegistry

from genesis.core.transport.base_transport import BaseTransport


INSTRUMENT_TYPE_KEY = "sr850"


class Sr850Instrument(BaseInstrument):
    displayName = "SRS SR850 Lock-in Amplifier"
    _COMMAND_BY_CONFIG_KEY: dict[str, str] = {
        "referenceModeIndex": "FMOD",
        "referenceFrequencyHz": "FREQ",
        "referenceOutputAmplitudeVrms": "SLVL",
        "referencePhaseDeg": "PHAS",
        "inputConfigurationIndex": "ISRC",
        "inputCouplingIndex": "ICPL",
        "inputShieldGroundIndex": "IGND",
        "lineNotchFilterIndex": "ILIN",
        "sensitivityIndex": "SENS",
        "dynamicReserveModeIndex": "RMOD",
        "dynamicReserveIndex": "RSRV",
        "timeConstantIndex": "OFLT",
        "lowPassSlopeIndex": "OFSL",
    }
    _MEASUREMENT_INDEX_BY_KEY: dict[str, int] = {
        "x": 1,
        "y": 2,
        "r": 3,
        "theta": 4,
    }

    @classmethod
    def getDefaultTransportKey(cls) -> str:
        return "visa"

    @classmethod
    def getSupportedTransportKeys(cls) -> list[str]:
        return ["visa"]

    @classmethod
    def getDefaultAddress(cls) -> str:
        # SR850 manual: default GPIB address is 8.
        return "GPIB0::8::INSTR"

    @classmethod
    def getAvailableMeasurementSignals(cls) -> list[tuple[str, str]]:
        # Standard lock-in outputs; keys here are what jobs will store.
        return [
            ("x", "X (in-phase)"),
            ("y", "Y (quadrature)"),
            ("r", "R (magnitude)"),
            ("theta", "θ (phase, deg)"),
        ]

    @classmethod
    def getAvailablePlotSignals(cls) -> list[tuple[str, str]]:
        # Same set is reasonable to plot in most cases.
        return cls.getAvailableMeasurementSignals()

    @classmethod
    def getJobConfigFields(cls) -> list[ConfigFieldDefinition]:
        # Note: These fields are configuration parameters that will be
        # persisted into the job JSON. They intentionally do NOT encode
        # instrument behavior/command sequences (that lives in the driver).
        sensitivityChoices = [
            ConfigChoice(0, "2 nV (0)"),
            ConfigChoice(1, "5 nV (1)"),
            ConfigChoice(2, "10 nV (2)"),
            ConfigChoice(3, "20 nV (3)"),
            ConfigChoice(4, "50 nV (4)"),
            ConfigChoice(5, "100 nV (5)"),
            ConfigChoice(6, "200 nV (6)"),
            ConfigChoice(7, "500 nV (7)"),
            ConfigChoice(8, "1 µV (8)"),
            ConfigChoice(9, "2 µV (9)"),
            ConfigChoice(10, "5 µV (10)"),
            ConfigChoice(11, "10 µV (11)"),
            ConfigChoice(12, "20 µV (12)"),
            ConfigChoice(13, "50 µV (13)"),
            ConfigChoice(14, "100 µV (14)"),
            ConfigChoice(15, "200 µV (15)"),
            ConfigChoice(16, "500 µV (16)"),
            ConfigChoice(17, "1 mV (17)"),
            ConfigChoice(18, "2 mV (18)"),
            ConfigChoice(19, "5 mV (19)"),
            ConfigChoice(20, "10 mV (20)"),
            ConfigChoice(21, "20 mV (21)"),
            ConfigChoice(22, "50 mV (22)"),
            ConfigChoice(23, "100 mV (23)"),
            ConfigChoice(24, "200 mV (24)"),
            ConfigChoice(25, "500 mV (25)"),
            ConfigChoice(26, "1 V (26)"),
        ]

        timeConstantChoices = [
            ConfigChoice(0, "10 µs (0)"),
            ConfigChoice(1, "30 µs (1)"),
            ConfigChoice(2, "100 µs (2)"),
            ConfigChoice(3, "300 µs (3)"),
            ConfigChoice(4, "1 ms (4)"),
            ConfigChoice(5, "3 ms (5)"),
            ConfigChoice(6, "10 ms (6)"),
            ConfigChoice(7, "30 ms (7)"),
            ConfigChoice(8, "100 ms (8)"),
            ConfigChoice(9, "300 ms (9)"),
            ConfigChoice(10, "1 s (10)"),
            ConfigChoice(11, "3 s (11)"),
            ConfigChoice(12, "10 s (12)"),
            ConfigChoice(13, "30 s (13)"),
            ConfigChoice(14, "100 s (14)"),
            ConfigChoice(15, "300 s (15)"),
            ConfigChoice(16, "1 ks (16)"),
            ConfigChoice(17, "3 ks (17)"),
            ConfigChoice(18, "10 ks (18)"),
            ConfigChoice(19, "30 ks (19)"),
        ]

        dynamicReserveChoices = [
            ConfigChoice(0, "Reserve 0 (0)"),
            ConfigChoice(1, "Reserve 1 (1)"),
            ConfigChoice(2, "Reserve 2 (2)"),
            ConfigChoice(3, "Reserve 3 (3)"),
            ConfigChoice(4, "Reserve 4 (4)"),
            ConfigChoice(5, "Reserve 5 (5)"),
        ]

        return [
            ConfigFieldDefinition(
                key="referenceModeIndex",
                label="Reference Mode",
                fieldType="enum",
                default=0,
                choices=[
                    ConfigChoice(0, "Internal"),
                    ConfigChoice(1, "Internal Sweep"),
                    ConfigChoice(2, "External"),
                ],
                helpText="Maps to SR850 reference mode (e.g. FMOD mode index per manual).",
            ),
            ConfigFieldDefinition(
                key="referenceFrequencyHz",
                label="Reference Frequency (Hz)",
                fieldType="float",
                default=1000.0,
                minValue=0.0,
                maxValue=1e9,
                stepValue=0.1,
                helpText="Reference frequency setpoint used by the SR850 reference generator.",
                sweepable=True,
            ),
            ConfigFieldDefinition(
                key="referenceOutputAmplitudeVrms",
                label="Sine Output Amplitude (Vrms)",
                fieldType="float",
                default=1.0,
                minValue=0.004,
                maxValue=5.0,
                stepValue=0.002,
                helpText="Sine output amplitude (SLVL command). Range 0.004 to 5.000 Vrms (rounded to 0.002 V).",
                sweepable=True,
            ),
            ConfigFieldDefinition(
                key="referencePhaseDeg",
                label="Reference Phase (deg)",
                fieldType="float",
                default=0.0,
                minValue=-360.0,
                maxValue=360.0,
                stepValue=0.1,
                helpText="Phase shift (PHAS command).",
                sweepable=True,
            ),
            ConfigFieldDefinition(
                key="inputConfigurationIndex",
                label="Input Configuration Index",
                fieldType="enum",
                default=0,
                choices=[
                    ConfigChoice(0, "A"),
                    ConfigChoice(1, "A-B"),
                    ConfigChoice(2, "I"),
                ],
                helpText="Input config (ISRC command).",
            ),
            ConfigFieldDefinition(
                key="inputCouplingIndex",
                label="Input Coupling",
                fieldType="enum",
                default=0,
                choices=[
                    ConfigChoice(0, "AC (0)"),
                    ConfigChoice(1, "DC (1)"),
                ],
                helpText="Input coupling (ICPL command): AC (0) or DC (1).",
            ),
            ConfigFieldDefinition(
                key="inputShieldGroundIndex",
                label="Input Shield Grounding",
                fieldType="enum",
                default=0,
                choices=[
                    ConfigChoice(0, "Float (0)"),
                    ConfigChoice(1, "Ground (1)"),
                ],
                helpText="Input shield grounding (IGND command): Float (0) or Ground (1).",
            ),
            ConfigFieldDefinition(
                key="lineNotchFilterIndex",
                label="Line Notch Filter",
                fieldType="enum",
                default=0,
                choices=[
                    ConfigChoice(0, "Out"),
                    ConfigChoice(1, "Line In"),
                    ConfigChoice(2, "2x Line In"),
                    ConfigChoice(3, "Both"),
                ],
                helpText="Line notch filter selection (ILIN command).",
            ),
            ConfigFieldDefinition(
                key="sensitivityIndex",
                label="Sensitivity",
                fieldType="enum",
                default=26,
                choices=sensitivityChoices,
                helpText="Full-scale sensitivity (SENS command).",
            ),
            ConfigFieldDefinition(
                key="dynamicReserveModeIndex",
                label="Dynamic Reserve Mode",
                fieldType="enum",
                default=2,
                choices=[
                    ConfigChoice(0, "Max"),
                    ConfigChoice(1, "Manual"),
                    ConfigChoice(2, "Min"),
                ],
                helpText="Dynamic reserve mode (RMOD command).",
            ),
            ConfigFieldDefinition(
                key="dynamicReserveIndex",
                label="Dynamic Reserve",
                fieldType="enum",
                default=3,
                choices=dynamicReserveChoices,
                helpText="Dynamic reserve setting (RSRV command; selecting a value switches to Manual reserve mode).",
            ),
            ConfigFieldDefinition(
                key="timeConstantIndex",
                label="Time Constant",
                fieldType="enum",
                default=8,
                choices=timeConstantChoices,
                helpText="Time constant (OFLT command).",
            ),
            ConfigFieldDefinition(
                key="lowPassSlopeIndex",
                label="Low Pass Filter Slope",
                fieldType="enum",
                default=1,
                choices=[
                    ConfigChoice(0, "6 dB/oct"),
                    ConfigChoice(1, "12 dB/oct"),
                    ConfigChoice(2, "18 dB/oct"),
                    ConfigChoice(3, "24 dB/oct"),
                ],
                helpText="Low-pass slope (OFSL command).",
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
        # Apply all configured values through the same path used by sweeps.
        for key, value in self.jobConfig.items():
            self.applyConfigValue(str(key), value)

    def applySafeState(self) -> None:
        # Prefer explicit safe configuration; fallback to current job config.
        target = self._safeConfig or self.jobConfig
        for key, value in target.items():
            self.applyConfigValue(str(key), value)

    def readMeasurements(self, signalKeys: list[str]) -> dict[str, float]:
        # Always read from instrument/query response; never synthesize values here.
        return self._readMeasurementsViaVisa(signalKeys)

    def applyConfigValue(self, key: str, value: float | int | str) -> None:
        self.jobConfig[key] = value
        commandName = self._COMMAND_BY_CONFIG_KEY.get(key)
        if commandName is None:
            return
        formatted = self._formatCommandValue(value)
        self.transport.write(f"{commandName} {formatted}")

    def _formatCommandValue(self, value: float | int | str) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return str(value)
        return f"{float(value):.12g}"

    def _readMeasurementsViaVisa(self, signalKeys: list[str]) -> dict[str, float]:
        requested = [k for k in signalKeys if k in self._MEASUREMENT_INDEX_BY_KEY]
        if not requested:
            return {}

        channelList = ",".join(
            str(self._MEASUREMENT_INDEX_BY_KEY[k]) for k in requested
        )
        response = self.transport.query(f"SNAP? {channelList}")
        parts = [p.strip() for p in response.split(",")]
        values: dict[str, float] = {}

        for key, raw in zip(requested, parts):
            try:
                values[key] = float(raw)
            except ValueError:
                continue
        return values


def _sr850Factory(
    name: str,
    transport: BaseTransport,
    metadata: dict[str, Any] | None = None,
    jobConfig: dict[str, Any] | None = None,
) -> BaseInstrument:
    # Factory wrapper used by the instrument registry.
    return Sr850Instrument(
        name=name,
        transport=transport,
        metadata=metadata,
        jobConfig=jobConfig,
    )


def registerInstruments(registry: InstrumentRegistry) -> None:
    registry.registerInstrument(
        key=INSTRUMENT_TYPE_KEY,
        instrumentType=Sr850Instrument,
        factory=_sr850Factory,
    )
