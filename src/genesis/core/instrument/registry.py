from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, TypeVar

from .base_instrument import BaseInstrument

InstrumentFactory = Callable[..., BaseInstrument]
_TInstrument = TypeVar("_TInstrument", bound=BaseInstrument)


@dataclass(frozen=True, slots=True)
class InstrumentRegistration:
    instrumentType: type[BaseInstrument]
    factory: InstrumentFactory


class InstrumentRegistry:
    """
    Registry mapping logical instrument identifiers to factories.
    """

    def __init__(self) -> None:
        self._registrations: Dict[str, InstrumentRegistration] = {}

    def registerInstrument(
        self, key: str, instrumentType: type[BaseInstrument], factory: InstrumentFactory
    ) -> None:
        if key in self._registrations:
            raise ValueError(f"Instrument key already registered: {key!r}")
        self._registrations[key] = InstrumentRegistration(
            instrumentType=instrumentType, factory=factory
        )

    def createInstrument(self, key: str, *args, **kwargs) -> BaseInstrument:
        try:
            registration = self._registrations[key]
        except KeyError as exc:  # pragma: no cover - trivial
            raise KeyError(f"Unknown instrument key: {key!r}") from exc
        return registration.factory(*args, **kwargs)

    def getInstrumentType(self, key: str) -> type[BaseInstrument]:
        try:
            return self._registrations[key].instrumentType
        except KeyError as exc:  # pragma: no cover - trivial
            raise KeyError(f"Unknown instrument key: {key!r}") from exc

    def hasInstrument(self, key: str) -> bool:
        return key in self._registrations

    def listInstruments(self) -> list[str]:
        return sorted(self._registrations.keys())
