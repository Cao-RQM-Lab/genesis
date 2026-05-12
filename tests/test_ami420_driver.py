from __future__ import annotations

import unittest
from typing import Iterable

from genesis.core.transport.base_transport import BaseTransport
from genesis.core.transport.dummy_test_transport import DummyTestTransport
from genesis.instruments.ami420.driver import Ami420Instrument


class _ScriptedTransport(BaseTransport):
    """Test transport that returns scripted query responses in order."""

    def __init__(self, responsesByCommand: dict[str, Iterable[str]]) -> None:
        super().__init__(resourceName="MOCK")
        self.writtenCommands: list[str] = []
        self._pending: dict[str, list[str]] = {
            key: list(values) for key, values in responsesByCommand.items()
        }
        self._lastWrite: str | None = None

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def write(self, command: str) -> None:
        self.writtenCommands.append(str(command))
        self._lastWrite = str(command).strip()

    def read(self) -> str:
        if self._lastWrite is None:
            return "0"
        # Match either the full or the abbreviated form by canonical prefix.
        for key, values in self._pending.items():
            if self._lastWrite.startswith(key) and values:
                return values.pop(0)
        # Default response is "0" so float() does not raise.
        return "0"


class Ami420DriverTests(unittest.TestCase):
    def test_apply_target_field_issues_program_and_ramp(self) -> None:
        transport = _ScriptedTransport({})
        instrument = Ami420Instrument(name="magnet", transport=transport)
        instrument.applyConfigValue("targetFieldT", 1.5)
        writes = transport.writtenCommands
        self.assertIn("CONF:FIELD:PROG 1.5", writes)
        self.assertEqual(writes[-1], "RAMP")

    def test_apply_safe_state_ramps_to_zero(self) -> None:
        transport = _ScriptedTransport({})
        instrument = Ami420Instrument(
            name="magnet",
            transport=transport,
            metadata={"safeConfig": {"targetFieldT": 0.0}},
            jobConfig={"targetFieldT": 2.0},
        )
        instrument.applySafeState()
        writes = transport.writtenCommands
        self.assertIn("CONF:FIELD:UNITS 1", writes)
        self.assertIn("CONF:FIELD:PROG 0", writes)
        self.assertEqual(writes[-1], "RAMP")
        self.assertEqual(instrument.jobConfig["targetFieldT"], 0.0)

    def test_initialize_forces_tesla_units_and_applies_target(self) -> None:
        transport = _ScriptedTransport({})
        instrument = Ami420Instrument(
            name="magnet",
            transport=transport,
            jobConfig={"targetFieldT": 0.5},
        )
        instrument.initialize()
        writes = transport.writtenCommands
        self.assertEqual(writes[0], "CONF:FIELD:UNITS 1")
        self.assertIn("CONF:FIELD:PROG 0.5", writes)
        self.assertEqual(writes[-1], "RAMP")

    def test_read_measurements_maps_keys_to_queries(self) -> None:
        transport = _ScriptedTransport(
            {
                "FIELD:MAG?": ["1.2345"],
                "CURR:MAG?": ["42.0"],
                "VOLT:MAG?": ["3.14"],
            }
        )
        instrument = Ami420Instrument(name="magnet", transport=transport)
        values = instrument.readMeasurements(
            ["magnetFieldT", "magnetCurrentA", "magnetVoltageV"]
        )
        self.assertAlmostEqual(values["magnetFieldT"], 1.2345)
        self.assertAlmostEqual(values["magnetCurrentA"], 42.0)
        self.assertAlmostEqual(values["magnetVoltageV"], 3.14)

    def test_wait_for_setpoint_completes_when_within_tolerance_and_holding(
        self,
    ) -> None:
        # Field starts away, then converges to target; STATE? reports HOLDING.
        transport = _ScriptedTransport(
            {
                "FIELD:MAG?": ["0.0", "0.5", "1.0", "1.0"],
                "STATE?": ["1", "1", "1", "2"],
            }
        )
        instrument = Ami420Instrument(
            name="magnet",
            transport=transport,
            jobConfig={
                "targetFieldT": 1.0,
                "setpointToleranceT": 0.01,
                "setpointTimeoutSeconds": 10.0,
                "setpointPollIntervalSeconds": 0.05,
            },
        )
        progress: list[float] = []
        result = instrument.waitForSetpoint(
            key="targetFieldT",
            target_value=1.0,
            should_stop=None,
            on_progress=progress.append,
        )
        self.assertTrue(result)
        self.assertEqual(progress[-1], 1.0)

    def test_wait_for_setpoint_respects_should_stop(self) -> None:
        transport = _ScriptedTransport(
            {
                "FIELD:MAG?": ["0.0"] * 20,
                "STATE?": ["1"] * 20,
            }
        )
        instrument = Ami420Instrument(
            name="magnet",
            transport=transport,
            jobConfig={
                "targetFieldT": 1.0,
                "setpointToleranceT": 0.0,
                "setpointTimeoutSeconds": 0.0,
                "setpointPollIntervalSeconds": 0.05,
            },
        )
        calls = {"count": 0}

        def _should_stop() -> bool:
            calls["count"] += 1
            return calls["count"] >= 2

        result = instrument.waitForSetpoint(
            key="targetFieldT",
            target_value=1.0,
            should_stop=_should_stop,
            on_progress=None,
        )
        self.assertFalse(result)

    def test_wait_for_setpoint_timeout_fails_gracefully(self) -> None:
        transport = _ScriptedTransport(
            {
                "FIELD:MAG?": ["0.0"] * 50,
                "STATE?": ["1"] * 50,
            }
        )
        instrument = Ami420Instrument(
            name="magnet",
            transport=transport,
            jobConfig={
                "targetFieldT": 1.0,
                "setpointToleranceT": 0.0,
                "setpointTimeoutSeconds": 0.05,
                "setpointPollIntervalSeconds": 0.05,
            },
        )
        result = instrument.waitForSetpoint(
            key="targetFieldT",
            target_value=1.0,
            should_stop=None,
            on_progress=None,
        )
        self.assertFalse(result)

    def test_wait_for_setpoint_aborts_on_quench(self) -> None:
        transport = _ScriptedTransport(
            {
                "FIELD:MAG?": ["0.5"],
                "STATE?": ["7"],
            }
        )
        instrument = Ami420Instrument(
            name="magnet",
            transport=transport,
            jobConfig={
                "targetFieldT": 1.0,
                "setpointToleranceT": 0.001,
                "setpointTimeoutSeconds": 10.0,
                "setpointPollIntervalSeconds": 0.05,
            },
        )
        result = instrument.waitForSetpoint(
            key="targetFieldT",
            target_value=1.0,
            should_stop=None,
            on_progress=None,
        )
        self.assertFalse(result)

    def test_wait_for_setpoint_is_noop_for_other_keys(self) -> None:
        transport = _ScriptedTransport({})
        instrument = Ami420Instrument(name="magnet", transport=transport)
        result = instrument.waitForSetpoint(
            key="setpointToleranceT",
            target_value=0.0,
        )
        self.assertTrue(result)

    def test_finalize_initialization_converges_on_dummy_transport(self) -> None:
        transport = DummyTestTransport("DUMMY")
        instrument = Ami420Instrument(
            name="mag",
            transport=transport,
            jobConfig={
                "targetFieldT": 1.0,
                "setpointToleranceT": 0.05,
                "setpointTimeoutSeconds": 60.0,
                "setpointPollIntervalSeconds": 0.01,
            },
        )
        instrument.applyConfigValue("targetFieldT", 1.0)
        self.assertTrue(instrument.finalizeInitialization(lambda: False))
        sample = float(transport.query("FIELD:MAG?").strip())
        self.assertAlmostEqual(sample, 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
