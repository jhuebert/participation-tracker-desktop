"""File + console logging, an in-memory tail, and an excepthook.

With ``--windowed`` PyInstaller builds there is no console, so everything of
interest lands in ``participation_tracker.log`` next to the exe.
"""

from __future__ import annotations

import logging
import sys
from collections import deque
from collections.abc import Callable

from . import config

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_recent: deque[str] = deque(maxlen=500)


class _DequeHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _recent.append(self.format(record))
        except Exception:  # pragma: no cover - logging must never raise
            pass


def recent_lines() -> list[str]:
    """Return the most recent formatted log lines (for a future View Log UI)."""
    return list(_recent)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_pt_configured", False):
        return
    root.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT)

    try:
        file_handler = logging.FileHandler(config.log_path(), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass  # cannot write a log file; carry on with console/deque only

    # A console handler only makes sense when there is a console.
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    deque_handler = _DequeHandler()
    deque_handler.setFormatter(formatter)
    root.addHandler(deque_handler)

    root._pt_configured = True  # type: ignore[attr-defined]


def install_excepthook(on_error: Callable[[BaseException], None] | None = None) -> None:
    """Log uncaught exceptions and optionally surface them to the UI."""
    log = logging.getLogger("participation_tracker")

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
        if on_error is not None:
            try:
                on_error(exc_value)
            except Exception:  # pragma: no cover
                pass

    sys.excepthook = _hook
