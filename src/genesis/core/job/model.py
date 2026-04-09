from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class JobModel:
    """
    In-memory representation of a single job loaded from JSON.

    This is intentionally minimal; the shape will evolve with real jobs.
    """

    jobId: str
    rawDefinition: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def fromJson(cls, payload: dict[str, Any]) -> "JobModel":
        """
        Build a `JobModel` from a parsed JSON job description.
        """
        jobId = str(payload.get("jobId", "unnamed-job"))
        return cls(jobId=jobId, rawDefinition=payload)
