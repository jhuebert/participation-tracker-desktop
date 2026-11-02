"""Chime playback for student picks.

The bundled ``assets/chime.wav`` is played through Windows' built-in
``winsound`` so no extra runtime dependency or DLL ships with the exe, and
playback never blocks the interface.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from .config import app_dir

log = logging.getLogger(__name__)

CHIME_FILENAME = "chime.wav"


def chime_path() -> Path | None:
    """Location of the bundled chime, or ``None`` when it is unavailable."""
    if getattr(sys, "frozen", False):
        # PyInstaller unpacks datas under ``sys._MEIPASS``.
        candidate = Path(getattr(sys, "_MEIPASS", "")) / "assets" / CHIME_FILENAME
        return candidate if candidate.is_file() else None
    candidate = app_dir() / "assets" / CHIME_FILENAME
    return candidate if candidate.is_file() else None


def play_chime() -> None:
    """Play the pick chime without blocking the interface (Windows only)."""
    if sys.platform != "win32":
        return
    path = chime_path()
    if path is None:
        log.debug("Chime skipped: %s not found", CHIME_FILENAME)
        return
    try:
        import winsound

        winsound.PlaySound(
            str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )
    except Exception:  # noqa: BLE001 - a missing sound must never break a pick
        log.debug("Chime playback failed", exc_info=True)