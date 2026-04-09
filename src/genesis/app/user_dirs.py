from __future__ import annotations

"""
Standard user-local folders for Genesis (under the OS Documents directory).

Created on startup; used as defaults for job JSON and raw data export dialogs.
"""

from pathlib import Path

from PySide6.QtCore import QStandardPaths


def genesis_user_root() -> Path:
    docs = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
    )
    return docs / "Genesis"


def genesis_jobs_dir() -> Path:
    return genesis_user_root() / "jobs"


def genesis_runs_dir() -> Path:
    return genesis_user_root() / "runs"


def ensure_genesis_user_directories() -> None:
    """Ensure ~/Documents/Genesis, .../jobs, and .../runs exist."""
    genesis_jobs_dir().mkdir(parents=True, exist_ok=True)
    genesis_runs_dir().mkdir(parents=True, exist_ok=True)
