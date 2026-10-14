"""Filesystem locations and application constants.

The SQLite database lives *next to the exe* (or the project root when run from
source). If that folder is not writable we fall back to
``%LOCALAPPDATA%\\ParticipationTracker``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DB_FILENAME = "participation_tracker.db"
LOG_FILENAME = "participation_tracker.log"

APP_NAME = "Participation Tracker"


def app_dir() -> Path:
    """Directory that should hold the DB/log.

    Frozen (PyInstaller ``--onefile``) unpacks code to a temp dir, so
    ``__file__`` is meaningless there; ``sys.executable`` is the real exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]  # project root when run from source


def _is_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("")
        probe.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    """Prefer the exe's folder; fall back to LOCALAPPDATA if not writable."""
    d = app_dir()
    if _is_writable(d):
        return d
    fallback = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ParticipationTracker"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def log_path() -> Path:
    return data_dir() / LOG_FILENAME


def uses_fallback_dir() -> bool:
    """True when the exe/project folder is not writable and we fell back."""
    return not _is_writable(app_dir())


# --- Session / behaviour constants -----------------------------------------

MARGIN = 24  # overlay margin from the work-area edge, in physical pixels
