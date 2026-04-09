from __future__ import annotations

import threading


class AbortController:
    """
    Cooperative abort signaling for running jobs.
    """

    def __init__(self) -> None:
        self._abortEvent = threading.Event()

    def requestAbort(self) -> None:
        """
        Signal that the current job should abort as soon as safely possible.
        """
        self._abortEvent.set()

    def clearAbort(self) -> None:
        """
        Clear any previous abort signal.
        """
        self._abortEvent.clear()

    def isAbortRequested(self) -> bool:
        return self._abortEvent.is_set()
