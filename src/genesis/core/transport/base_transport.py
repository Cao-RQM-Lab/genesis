from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TransportSettingsLike(Protocol):
    """
    Lightweight protocol for settings mappings.
    """

    def get(
        self, key: str, default: Any | None = None
    ) -> Any | None:  # pragma: no cover - trivial
        ...


class BaseTransport(ABC):
    """
    Abstract base for all low-level communication transports.

    Transports hide the concrete communication layer (e.g. VISA)
    from higher-level instruments.
    """

    def __init__(
        self, resourceName: str, settings: TransportSettingsLike | None = None
    ) -> None:
        self.resourceName = resourceName
        self.settings = settings

    @abstractmethod
    def open(self) -> None:
        """
        Open the underlying connection.
        """

    @abstractmethod
    def close(self) -> None:
        """
        Close the underlying connection.
        """

    @abstractmethod
    def write(self, command: str) -> None:
        """
        Write a command to the instrument.
        """

    @abstractmethod
    def read(self) -> str:
        """
        Read a response from the instrument.
        """

    def query(self, command: str) -> str:
        """
        Convenience helper performing write + read.
        """
        self.write(command)
        return self.read()
