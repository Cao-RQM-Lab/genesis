from __future__ import annotations

import unittest

from genesis.core.instrument.base_instrument import BaseInstrument
from genesis.core.instrument.config_field import ConfigFieldDefinition
from genesis.core.runtime.setpoint_safety import (
    SetpointSafetyController,
    build_value_bounds_by_instrument,
)
from genesis.core.transport.base_transport import BaseTransport


class _FakeTransport(BaseTransport):
    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def write(self, command: str) -> None:
        return None

    def read(self) -> str:
        return "0"


class _FakeInstrument(BaseInstrument):
    @classmethod
    def getJobConfigFields(cls) -> list[ConfigFieldDefinition]:
        return [
            ConfigFieldDefinition(
                key="setpoint",
                label="Setpoint",
                fieldType="float",
                default=0.0,
                minValue=-10.0,
                maxValue=10.0,
                sweepable=True,
            )
        ]

    def __init__(self) -> None:
        super().__init__(name="fake", transport=_FakeTransport("fake"))
        self.values: list[float] = []

    def initialize(self) -> None:
        return None

    def applySafeState(self) -> None:
        return None

    def applyConfigValue(self, key: str, value: float | int | str) -> None:
        if key == "setpoint":
            self.values.append(float(value))


class SetpointSafetyControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sleepCalls: list[float] = []
        bounds = build_value_bounds_by_instrument({"dev": _FakeInstrument})
        self.controller = SetpointSafetyController(
            bounds, sleep_fn=lambda seconds: self.sleepCalls.append(float(seconds))
        )
        self.instrument = _FakeInstrument()

    def test_clamps_to_min_max(self) -> None:
        self.controller.apply_bounded_immediate(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            value=999.0,
        )
        self.assertEqual(self.instrument.values[-1], 10.0)

    def test_initialization_transition_uses_step_size_and_slew_rate(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", 0.0)
        self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=1.0,
            max_slew_rate=2.0,
            max_slew_step=0.2,
        )
        # 1.0 / 0.2 => 5 steps, first command immediate then 4 waits.
        self.assertEqual(len(self.instrument.values), 5)
        self.assertEqual(len(self.sleepCalls), 4)
        self.assertTrue(all(abs(s - 0.1) < 1e-9 for s in self.sleepCalls))
        self.assertAlmostEqual(self.instrument.values[-1], 1.0, places=9)

    def test_ramp_up_is_monotonic_and_bounded(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", 0.0)
        self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=5.0,
            max_slew_rate=10.0,
            max_slew_step=1.0,
        )
        self.assertTrue(
            all(
                a <= b
                for a, b in zip(self.instrument.values, self.instrument.values[1:])
            )
        )
        self.assertTrue(all(-10.0 <= v <= 10.0 for v in self.instrument.values))
        self.assertAlmostEqual(self.instrument.values[-1], 5.0, places=9)

    def test_ramp_down_is_monotonic_and_bounded(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", 5.0)
        self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=-5.0,
            max_slew_rate=10.0,
            max_slew_step=1.0,
        )
        self.assertTrue(
            all(
                a >= b
                for a, b in zip(self.instrument.values, self.instrument.values[1:])
            )
        )
        self.assertTrue(all(-10.0 <= v <= 10.0 for v in self.instrument.values))
        self.assertAlmostEqual(self.instrument.values[-1], -5.0, places=9)

    def test_no_intermediate_value_exceeds_target_or_bounds(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", -2.0)
        self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=8.0,
            max_slew_rate=20.0,
            max_slew_step=0.5,
        )
        self.assertTrue(all(-10.0 <= v <= 10.0 for v in self.instrument.values))
        self.assertTrue(all(v <= 8.0 for v in self.instrument.values))
        self.assertEqual(self.instrument.values[-1], 8.0)

    def test_zero_or_negative_slew_rate_means_single_bounded_write(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", 0.0)
        self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=1.2,
            max_slew_rate=0.0,
            max_slew_step=0.1,
        )
        self.assertEqual(self.instrument.values, [1.2])

    def test_abort_interrupts_ramp(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", 0.0)
        completed = self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=9.0,
            max_slew_rate=1.0,
            max_slew_step=0.1,
            should_stop=lambda: True,
        )
        self.assertFalse(completed)
        self.assertEqual(self.instrument.values, [])

    def test_large_sweep_step_still_ramps_by_max_slew_step(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", 0.0)
        self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=1.0,
            max_slew_rate=2.0,
            max_slew_step=0.25,
        )
        self.assertEqual(len(self.instrument.values), 4)
        self.assertAlmostEqual(self.instrument.values[-1], 1.0, places=9)

    def test_below_max_slew_step_uses_single_command(self) -> None:
        self.controller.seed_last_value("dev", "setpoint", 0.0)
        self.controller.apply_slew_limited(
            instrument_id="dev",
            instrument=self.instrument,
            key="setpoint",
            target_value=0.05,
            max_slew_rate=1.0,
            max_slew_step=0.1,
        )
        self.assertEqual(self.instrument.values, [0.05])
        self.assertEqual(self.sleepCalls, [])


if __name__ == "__main__":
    unittest.main()
