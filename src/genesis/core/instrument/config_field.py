from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ConfigChoice:
    value: Any
    label: str


@dataclass(frozen=True, slots=True)
class ConfigFieldDefinition:
    """
    Declarative definition of a single instrument configuration parameter.

    This is used by the job builder GUI to render the right widget(s) and
    by the job serialization layer to store user-provided values.

    Instrument *behavior* (which GPIB commands to send) lives in the instrument
    driver, not in JSON config files shipped with the project.
    """

    key: str
    label: str
    fieldType: str
    default: Any
    helpText: str = ""
    minValue: float | int | None = None
    maxValue: float | int | None = None
    stepValue: float | int | None = None
    choices: list[ConfigChoice] | None = None
    sweepable: bool = False
