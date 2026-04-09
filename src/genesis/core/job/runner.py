from __future__ import annotations

import threading
from typing import Iterable

from .abort_controller import AbortController
from .model import JobModel
from .safe_state_manager import SafeStateManager
from genesis.core.instrument.base_instrument import BaseInstrument


class JobRunner(threading.Thread):
    """
    Threaded job execution skeleton.

    Real step execution and scheduling will be added later.
    """

    def __init__(
        self,
        jobModel: JobModel,
        abortController: AbortController,
        instruments: Iterable[BaseInstrument],
        safeStateManager: SafeStateManager | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.jobModel = jobModel
        self.abortController = abortController
        self.instruments = list(instruments)
        self.safeStateManager = safeStateManager or SafeStateManager()

    def run(self) -> None:
        """
        Thread entry point.

        The implementation is intentionally minimal and does not yet execute
        real job steps. It only demonstrates abort polling and safe-state
        handling.
        """
        try:
            # TODO: iterate over real job steps and perform instrument actions.
            while not self.abortController.isAbortRequested():
                # Placeholder for work; in a real runner this would perform
                # step logic and periodically check for abort.
                break
        finally:
            self.safeStateManager.ensureSafeState(self.instruments)
