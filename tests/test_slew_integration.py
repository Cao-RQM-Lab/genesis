from __future__ import annotations

import unittest

from genesis.core.instrument.base_instrument import BaseInstrument
from genesis.core.runtime.acquisition_worker import AcquisitionWorker
from genesis.core.runtime.setpoint_safety import (
    SetpointSafetyController,
    build_value_bounds_by_instrument,
)
from genesis.core.transport.base_transport import BaseTransport
from genesis.core.transport.dummy_test_transport import DummyTestTransport
from genesis.instruments.b29xx.driver import B29xxInstrument


def _extract_smu_voltage_writes(commands: list[str]) -> list[float]:
    values: list[float] = []
    prefix = ":SOUR1:VOLT "
    for command in commands:
        if command.startswith(prefix):
            values.append(float(command[len(prefix) :].strip()))
    return values


class _NoopTransport(BaseTransport):
    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def write(self, command: str) -> None:
        return None

    def read(self) -> str:
        return "0"


class _EventInstrument(BaseInstrument):
    @classmethod
    def getJobConfigFields(cls):
        return []

    def __init__(self, events: list[str]) -> None:
        super().__init__(name="evt", transport=_NoopTransport("noop"))
        self.events = events

    def initialize(self) -> None:
        return None

    def applySafeState(self) -> None:
        return None

    def applyConfigValue(self, key: str, value):
        self.events.append(f"write:{float(value):.6f}")


class _OrderWorker(AcquisitionWorker):
    def __init__(self, events: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._events = events

    def _sleepWithStop(self, seconds: float) -> None:
        self._events.append(f"settle:{seconds:.6f}")


class SlewIntegrationTests(unittest.TestCase):
    def test_b29xx_ramp_values_are_bounded_and_monotonic(self) -> None:
        transport = DummyTestTransport("DUMMY")
        instrument = B29xxInstrument(
            name="smu",
            transport=transport,
            jobConfig={"channel": 1, "forceMode": "VOLT"},
        )
        bounds = build_value_bounds_by_instrument({"smu": B29xxInstrument})
        safety = SetpointSafetyController(bounds, sleep_fn=lambda _s: None)
        safety.seed_last_value("smu", "forceVoltageLevelV", 0.0)

        completed = safety.apply_slew_limited(
            instrument_id="smu",
            instrument=instrument,
            key="forceVoltageLevelV",
            target_value=0.1,
            max_slew_rate=1.0,
            max_slew_step=0.05,
        )
        self.assertTrue(completed)

        writes = _extract_smu_voltage_writes(transport.writtenCommands)
        self.assertGreaterEqual(len(writes), 2)
        self.assertTrue(all(a <= b for a, b in zip(writes, writes[1:])))
        self.assertTrue(all(0.0 <= v <= 0.1 for v in writes))
        self.assertAlmostEqual(writes[-1], 0.1, places=9)

    def test_worker_uses_slew_limited_transitions(self) -> None:
        transport = DummyTestTransport("DUMMY")
        instrument = B29xxInstrument(
            name="smu",
            transport=transport,
            jobConfig={"channel": 1, "forceMode": "VOLT"},
        )
        sweeps = [
            {
                "instrumentId": "smu",
                "key": "forceVoltageLevelV",
                "start": 0.0,
                "stop": 0.1,
                "points": 2,
                "settleTimeSeconds": 0.0,
                "spacing": "linear",
                "stepSize": 0.2,
                "maxSlewRate": 1.0,
                "maxSlewStep": 0.05,
            }
        ]
        bounds = build_value_bounds_by_instrument({"smu": B29xxInstrument})
        worker = AcquisitionWorker(
            instrumentsById={"smu": instrument},
            measurementKeysByInstrumentId={"smu": []},
            sweeps=sweeps,
            intervalSeconds=0.0,
            initialSweepValuesByInstrumentId={"smu": {"forceVoltageLevelV": 0.0}},
            boundsByInstrumentId=bounds,
        )

        worker._runSingleSweep(sweeps[0])
        writes = _extract_smu_voltage_writes(transport.writtenCommands)
        self.assertGreaterEqual(len(writes), 2)
        self.assertTrue(all(-210.0 <= v <= 210.0 for v in writes))
        self.assertAlmostEqual(writes[-1], 0.1, places=9)

    def test_worker_small_delta_single_command(self) -> None:
        transport = DummyTestTransport("DUMMY")
        instrument = B29xxInstrument(
            name="smu",
            transport=transport,
            jobConfig={"channel": 1, "forceMode": "VOLT"},
        )
        sweeps = [
            {
                "instrumentId": "smu",
                "key": "forceVoltageLevelV",
                "start": 0.0,
                "stop": 0.05,
                "points": 2,
                "settleTimeSeconds": 0.0,
                "spacing": "linear",
                "stepSize": 0.05,
                "maxSlewRate": 1.0,
                "maxSlewStep": 0.1,
            }
        ]
        bounds = build_value_bounds_by_instrument({"smu": B29xxInstrument})
        worker = AcquisitionWorker(
            instrumentsById={"smu": instrument},
            measurementKeysByInstrumentId={"smu": []},
            sweeps=sweeps,
            intervalSeconds=0.0,
            initialSweepValuesByInstrumentId={"smu": {"forceVoltageLevelV": 0.0}},
            boundsByInstrumentId=bounds,
        )
        worker._runSingleSweep(sweeps[0])
        writes = _extract_smu_voltage_writes(transport.writtenCommands)
        # point1 writes 0.0; point2 should write directly to 0.05 once.
        self.assertEqual(writes[-1], 0.05)

    def test_worker_accepts_nested_2d_sweep_definition(self) -> None:
        transport = DummyTestTransport("DUMMY")
        instrument = B29xxInstrument(
            name="smu",
            transport=transport,
            jobConfig={"channel": 1, "forceMode": "VOLT"},
        )
        sweeps = [
            {
                "mode": "2d",
                "outer": {
                    "instrumentId": "smu",
                    "key": "forceVoltageLevelV",
                    "start": 0.0,
                    "stop": 0.1,
                    "points": 2,
                    "settleTimeSeconds": 0.0,
                    "spacing": "linear",
                    "stepSize": 0.1,
                    "maxSlewRate": 0.0,
                    "maxSlewStep": 0.1,
                },
                "inner": {
                    "instrumentId": "smu",
                    "key": "forceVoltageLevelV",
                    "start": 0.1,
                    "stop": 0.0,
                    "points": 2,
                    "settleTimeSeconds": 0.0,
                    "spacing": "linear",
                    "stepSize": 0.1,
                    "maxSlewRate": 0.0,
                    "maxSlewStep": 0.1,
                },
            }
        ]
        worker = AcquisitionWorker(
            instrumentsById={"smu": instrument},
            measurementKeysByInstrumentId={"smu": []},
            sweeps=sweeps,
            intervalSeconds=0.0,
            initialSweepValuesByInstrumentId={"smu": {"forceVoltageLevelV": 0.0}},
            boundsByInstrumentId=build_value_bounds_by_instrument(
                {"smu": B29xxInstrument}
            ),
        )
        completed = worker._runConfiguredSweep()
        self.assertTrue(completed)
        writes = _extract_smu_voltage_writes(transport.writtenCommands)
        self.assertGreaterEqual(len(writes), 4)

    def test_abort_interrupts_worker_slew(self) -> None:
        transport = DummyTestTransport("DUMMY")
        instrument = B29xxInstrument(
            name="smu",
            transport=transport,
            jobConfig={"channel": 1, "forceMode": "VOLT"},
        )
        sweeps = [
            {
                "instrumentId": "smu",
                "key": "forceVoltageLevelV",
                "start": 0.0,
                "stop": 0.2,
                "points": 2,
                "settleTimeSeconds": 0.0,
                "spacing": "linear",
                "stepSize": 0.2,
                "maxSlewRate": 0.1,
                "maxSlewStep": 0.01,
            }
        ]
        bounds = build_value_bounds_by_instrument({"smu": B29xxInstrument})
        worker = AcquisitionWorker(
            instrumentsById={"smu": instrument},
            measurementKeysByInstrumentId={"smu": []},
            sweeps=sweeps,
            intervalSeconds=0.0,
            initialSweepValuesByInstrumentId={"smu": {"forceVoltageLevelV": 0.0}},
            boundsByInstrumentId=bounds,
        )
        worker.requestStop()
        worker._runSingleSweep(sweeps[0])
        writes = _extract_smu_voltage_writes(transport.writtenCommands)
        self.assertEqual(writes, [])

    def test_settle_starts_after_ramp_completion(self) -> None:
        events: list[str] = []
        instrument = _EventInstrument(events)
        sweeps = [
            {
                "instrumentId": "dev",
                "key": "level",
                "start": 0.0,
                "stop": 0.2,
                "points": 2,
                "settleTimeSeconds": 0.5,
                "spacing": "linear",
                "stepSize": 0.2,
                "maxSlewRate": 1.0,
                "maxSlewStep": 0.05,
            }
        ]
        worker = _OrderWorker(
            events,
            instrumentsById={"dev": instrument},
            measurementKeysByInstrumentId={"dev": []},
            sweeps=sweeps,
            intervalSeconds=0.0,
            initialSweepValuesByInstrumentId={"dev": {"level": 0.0}},
            boundsByInstrumentId={},
        )
        worker._runSingleSweep(sweeps[0])
        settle_idx = next(i for i, e in enumerate(events) if e.startswith("settle:"))
        self.assertTrue(all(e.startswith("write:") for e in events[:settle_idx]))

    def test_stop_during_ramp_keeps_intermediate_active_value(self) -> None:
        transport = DummyTestTransport("DUMMY")
        instrument = B29xxInstrument(
            name="smu",
            transport=transport,
            jobConfig={"channel": 1, "forceMode": "VOLT"},
        )
        sweep = {
            "instrumentId": "smu",
            "key": "forceVoltageLevelV",
            "start": 0.0,
            "stop": 0.2,
            "points": 2,
            "settleTimeSeconds": 0.0,
            "spacing": "linear",
            "stepSize": 0.2,
            "maxSlewRate": 0.1,
            "maxSlewStep": 0.01,
        }
        worker = AcquisitionWorker(
            instrumentsById={"smu": instrument},
            measurementKeysByInstrumentId={"smu": []},
            sweeps=[sweep],
            intervalSeconds=0.0,
            initialSweepValuesByInstrumentId={"smu": {"forceVoltageLevelV": 0.0}},
            boundsByInstrumentId=build_value_bounds_by_instrument(
                {"smu": B29xxInstrument}
            ),
        )

        sleep_calls = {"count": 0}

        def _interrupt_sleep(_seconds: float) -> None:
            sleep_calls["count"] += 1
            if sleep_calls["count"] == 1:
                worker.requestStop()

        worker._safety._sleep = _interrupt_sleep
        worker._runSingleSweep(sweep)

        snapshot = worker.activeSweepValuesSnapshot()
        stopped_value = snapshot["smu"]["forceVoltageLevelV"]
        self.assertGreater(stopped_value, 0.0)
        self.assertLess(stopped_value, 0.2)
        writes = _extract_smu_voltage_writes(transport.writtenCommands)
        self.assertGreaterEqual(len(writes), 1)
        self.assertAlmostEqual(writes[-1], stopped_value, places=9)


if __name__ == "__main__":
    unittest.main()
