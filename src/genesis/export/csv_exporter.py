from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .base_exporter import BaseExporter
from genesis.core.job.model import JobModel


class CsvExporter(BaseExporter):
    """
    Simple CSV exporter skeleton.

    The payload format is intentionally loose for now and will be refined
    once real job outputs exist.
    """

    def __init__(
        self, outputPath: Path, fieldNames: Sequence[str] | None = None
    ) -> None:
        super().__init__(outputPath=outputPath)
        self.fieldNames = list(fieldNames) if fieldNames is not None else []

    def export(self, jobModel: JobModel, payload: Any) -> None:
        rows = self._normalizePayloadToRows(payload)
        if not rows:
            return

        fieldNames = self.fieldNames or list(rows[0].keys())
        self.outputPath.parent.mkdir(parents=True, exist_ok=True)

        with self.outputPath.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldNames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _normalizePayloadToRows(self, payload: Any) -> list[Mapping[str, Any]]:
        """
        Convert arbitrary payload into a list of row mappings.
        """
        if isinstance(payload, Mapping):
            return [payload]
        if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes)):
            rows: list[Mapping[str, Any]] = []
            for item in payload:
                if isinstance(item, Mapping):
                    rows.append(item)
            return rows
        return []
