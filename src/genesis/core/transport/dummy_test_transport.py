from __future__ import annotations

import random

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

    def open(self) -> None:
        self._isOpen = True
        print(f"[dummy-test:{self.resourceName}] OPEN")

    def close(self) -> None:
        if self._isOpen:
            print(f"[dummy-test:{self.resourceName}] CLOSE")
        self._isOpen = False

    def write(self, command: str) -> None:
        self.writtenCommands.append(str(command))
        print(f"[dummy-test:{self.resourceName}] WRITE {command}")

    def read(self) -> str:
        value = random.uniform(-1.0, 1.0)
        text = f"{value:.12g}"
        print(f"[dummy-test:{self.resourceName}] READ -> {text}")
        return text
