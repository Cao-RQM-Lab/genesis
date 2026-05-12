from __future__ import annotations

import random
import re

from genesis.core.transport.base_transport import BaseTransport


class DummyTestTransport(BaseTransport):
    """
    Test-only transport that does not talk to hardware.

    - write(): prints SCPI command to stdout
    - read()/query(): returns synthetic numeric string
    """

    def __init__(self, resourceName: str, settings: dict | None = None) -> None:
        super().__init__(resourceName=resourceName, settings=settings)
        self._isOpen = False
        self.writtenCommands: list[str] = []
        self._lastWrite: str | None = None

        # --- Optional AMI Model 420-like simulation (field ramps toward target) ---
        self._simField_T: float = 0.0
        self._simTargetField_T: float = 0.0
        # Fake coil: I (A) ≈ B (T) / (T/A); keep scale stable for tests.
        self._simTeslaPerAmp: float = 0.05

    def open(self) -> None:
        self._isOpen = True
        print(f"[dummy-test:{self.resourceName}] OPEN")

    def close(self) -> None:
        if self._isOpen:
            print(f"[dummy-test:{self.resourceName}] CLOSE")
        self._isOpen = False

    def write(self, command: str) -> None:
        self.writtenCommands.append(str(command))
        self._lastWrite = str(command).strip()
        print(f"[dummy-test:{self.resourceName}] WRITE {command}")
        cmd_u = self._lastWrite.upper()
        # PROGRAMMED FIELD (abbreviated/long-form SCPI)
        if ":FIELD:PROG" in cmd_u or "FIELD:PROGRAM" in cmd_u:
            m = re.search(r"([-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)", self._lastWrite)
            if m:
                self._simTargetField_T = float(m.group(1))

    def read(self) -> str:
        cmd = (self._lastWrite or "").strip()
        cmd_u = cmd.upper()

        # AMI-style queries: ramping field/current/voltage/state
        if "FIELD:MAG" in cmd_u and cmd_u.endswith("?"):
            text = f"{self._tick_simulated_field():.12g}"
            print(f"[dummy-test:{self.resourceName}] READ -> {text}")
            return text
        if cmd_u.endswith("STATE?") or cmd_u.endswith("STATE ?"):
            f = self._tick_simulated_field()
            tol = 1e-4
            if abs(f - self._simTargetField_T) <= tol:
                text = "2"
            else:
                text = "1"
            print(f"[dummy-test:{self.resourceName}] READ -> {text}")
            return text
        if "CURR:MAG" in cmd_u and cmd_u.endswith("?"):
            f = self._tick_simulated_field()
            amps = f / max(self._simTeslaPerAmp, 1e-12)
            text = f"{amps:.12g}"
            print(f"[dummy-test:{self.resourceName}] READ -> {text}")
            return text
        if "VOLT:MAG" in cmd_u and cmd_u.endswith("?"):
            f = self._tick_simulated_field()
            err = abs(f - self._simTargetField_T)
            volts = min(2.0, 0.02 + err * 0.5)
            text = f"{volts:.12g}"
            print(f"[dummy-test:{self.resourceName}] READ -> {text}")
            return text

        value = random.uniform(-1.0, 1.0)
        text = f"{value:.12g}"
        print(f"[dummy-test:{self.resourceName}] READ -> {text}")
        return text

    def _tick_simulated_field(self) -> float:
        """Move simulated field toward commanded target (simple exponential approach)."""
        delta = float(self._simTargetField_T) - float(self._simField_T)
        if abs(delta) < 1e-9:
            self._simField_T = float(self._simTargetField_T)
            return float(self._simField_T)
        step = delta * 0.35
        if abs(step) < 1e-12:
            step = 1e-9 if delta > 0 else -1e-9
        self._simField_T = float(self._simField_T) + step
        return float(self._simField_T)
