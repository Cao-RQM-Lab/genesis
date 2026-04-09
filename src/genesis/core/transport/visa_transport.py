from __future__ import annotations

from typing import Any

try:
    import pyvisa
except Exception:  # pragma: no cover - optional import
    pyvisa = None  # type: ignore[assignment]

from .base_transport import BaseTransport, TransportSettingsLike


class VisaTransport(BaseTransport):
    """
    pyvisa-based transport skeleton.

    Real IO will be implemented later once concrete instruments are in place.
    """

    def __init__(
        self, resourceName: str, settings: TransportSettingsLike | None = None
    ) -> None:
        super().__init__(resourceName=resourceName, settings=settings)
        self._resourceManager: Any | None = None
        self._resource: Any | None = None

    def open(self) -> None:
        """
        Open a VISA session for the configured resource.
        """
        if pyvisa is None:
            raise RuntimeError("pyvisa is not available; cannot open VISA transport.")

        self._resourceManager = pyvisa.ResourceManager()
        self._resource = self._resourceManager.open_resource(self.resourceName)
        # TODO: configure timeouts, termination, etc., via settings.

    def close(self) -> None:
        """
        Close the VISA session.
        """
        if self._resource is not None:
            try:
                self._resource.close()
            except Exception:
                # TODO: consider logging transport close failures.
                pass
        if self._resourceManager is not None:
            try:
                self._resourceManager.close()
            except Exception:
                pass
        self._resource = None
        self._resourceManager = None

    def write(self, command: str) -> None:
        if self._resource is None:
            raise RuntimeError("VISA resource is not open.")
        self._resource.write(command)

    def read(self) -> str:
        if self._resource is None:
            raise RuntimeError("VISA resource is not open.")
        response: str = self._resource.read()
        return response
