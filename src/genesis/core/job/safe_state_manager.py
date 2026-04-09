from __future__ import annotations

from typing import Iterable

from genesis.core.instrument.base_instrument import BaseInstrument


class SafeStateManager:
    """
    Coordinates bringing all instruments involved in a job into a safe state.
    """

    def __init__(self) -> None: ...

    def ensureSafeState(self, instruments: Iterable[BaseInstrument]) -> None:
        """
        Attempt to drive all instruments into a safe state.
        """
        for instrument in instruments:
            try:
                instrument.applySafeState()
            except Exception:
                # TODO: surface safe-state failures to the UI/logging layer.
                continue
