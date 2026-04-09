from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Type

from .base_exporter import BaseExporter
from .csv_exporter import CsvExporter


class ExportManager:
    """
    Simple registry for exporters keyed by name.
    """

    def __init__(self) -> None:
        self._exporters: Dict[str, Type[BaseExporter]] = {
            "csv": CsvExporter,
        }

    def registerExporter(self, key: str, exporterType: Type[BaseExporter]) -> None:
        if key in self._exporters:
            raise ValueError(f"Exporter already registered for key: {key!r}")
        self._exporters[key] = exporterType

    def createExporter(self, key: str, outputPath: Path, **kwargs: Any) -> BaseExporter:
        try:
            exporterType = self._exporters[key]
        except KeyError as exc:
            raise KeyError(f"Unknown exporter key: {key!r}") from exc
        return exporterType(outputPath=outputPath, **kwargs)
