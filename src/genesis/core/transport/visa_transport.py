from __future__ import annotations

from typing import Any

try:
    import pyvisa
except Exception:  # pragma: no cover - optional import
    pyvisa = None  # type: ignore[assignment]

from .base_transport import BaseTransport, TransportSettingsLike


class VisaTransport(BaseTransport):
    """
    pyvisa-based transport for GPIB/USB-TMC/VXI/LAN/etc.

    On ``open()`` applies sensible *message-based* defaults: newline terminators
    (IEEE 488.2 SCPI convention), timeouts, optional ``clear()``, and
    ``query()`` routes through PyVISA (more reliable than ad-hoc write+read for
    many GPIB adapters).

    Optional ``settings`` keys (typically job ``transportSettings`` merged with
    an instrument ``getDefaultTransportSettings()``):

    ``visaTimeoutMs`` (default ``10000``)
      Read/write timeout in milliseconds.

    ``writeTermination`` (default ``"\\n"``)
      Appended by PyVISA to each ``write()`` / ``query()`` program message.
      Empty string disables (raw).

    ``readTermination`` (default ``"\\n"``)
      Response reads stop at this terminator. Empty string disables (raw).

    ``visaQueryDelay`` (default ``0``)
      Seconds to wait after issuing a query command before ``read()`` (passed
      to ``resource.query``).

    ``visaClearOnOpen`` (default ``True``)
      Call ``resource.clear()`` after opening. Some hardware needs this after
      a previous fault; disable if your device rejects IEEE 488 clear.

    ``visaSendEndOnWrite`` (default ``True``)
      Sets ``resource.send_end`` when the resource supports it.
    """

    def __init__(
        self, resourceName: str, settings: TransportSettingsLike | None = None
    ) -> None:
        super().__init__(resourceName=resourceName, settings=settings)
        self._resourceManager: Any | None = None
        self._resource: Any | None = None

    def _setting(self, key: str, default: Any) -> Any:
        if self.settings is None:
            return default
        return self.settings.get(key, default)

    def open(self) -> None:
        """
        Open a VISA session for the configured resource.
        """
        if pyvisa is None:
            raise RuntimeError("pyvisa is not available; cannot open VISA transport.")

        self._resourceManager = pyvisa.ResourceManager()
        self._resource = self._resourceManager.open_resource(self.resourceName)
        self._configure_resource()

    def _configure_resource(self) -> None:
        if self._resource is None:
            return
        resource = self._resource
        resource.timeout = int(self._setting("visaTimeoutMs", 10000))

        write_term_raw = self._setting("writeTermination", "\n")
        resource.write_termination = (
            None
            if write_term_raw is None or write_term_raw == ""
            else str(write_term_raw)
        )

        read_term_raw = self._setting("readTermination", "\n")
        resource.read_termination = (
            None if read_term_raw is None or read_term_raw == "" else str(read_term_raw)
        )

        send_end = self._setting("visaSendEndOnWrite", True)
        if hasattr(resource, "send_end"):
            try:
                resource.send_end = bool(send_end)
            except Exception:
                pass

        if bool(self._setting("visaClearOnOpen", True)):
            try:
                resource.clear()
            except Exception:
                pass

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

    def query(self, command: str) -> str:
        if self._resource is None:
            raise RuntimeError("VISA resource is not open.")
        delay = float(self._setting("visaQueryDelay", 0.0))
        if delay > 0.0:
            text: str = self._resource.query(command, delay=delay)
        else:
            text = self._resource.query(command)
        return str(text)
