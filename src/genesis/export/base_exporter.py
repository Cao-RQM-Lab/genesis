from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from genesis.core.job.model import JobModel


class BaseExporter(ABC):
    """
    Abstract base for job data exporters.
    """

    def __init__(self, outputPath: Path) -> None:
        self.outputPath = outputPath

    @abstractmethod
    def export(self, jobModel: JobModel, payload: Any) -> None:
        """
        Export the provided payload for the given job.
        """
