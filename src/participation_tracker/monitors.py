"""Win32 physical-pixel monitor enumeration, with a non-Windows fallback."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys
from dataclasses import dataclass

MONITORINFOF_PRIMARY = 0x00000001
GA_ROOT = 2


@dataclass(frozen=True)
class Monitor:
    rect: tuple[int, int, int, int]
    work: tuple[int, int, int, int]
    primary: bool


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wt.DWORD)]


def enable_dpi_awareness() -> None:
    """Enable per-monitor DPI awareness outside Qt contexts (mostly tests)."""
    if sys.platform != "win32":
        return
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def get_monitors() -> list[Monitor]:
    if sys.platform != "win32":
        return []
    user32 = ctypes.windll.user32
    callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    enum_proc = callback_type(wt.BOOL, wt.HANDLE, wt.HDC, ctypes.POINTER(RECT), wt.LPARAM)
    monitors: list[Monitor] = []

    def callback(hmon, _hdc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            m, w = info.rcMonitor, info.rcWork
            monitors.append(Monitor((m.left, m.top, m.right, m.bottom), (w.left, w.top, w.right, w.bottom), bool(info.dwFlags & MONITORINFOF_PRIMARY)))
        return True

    user32.EnumDisplayMonitors(None, None, enum_proc(callback), 0)
    return monitors


def get_display_target(fallback_w: int, fallback_h: int) -> tuple[Monitor, bool]:
    fake = os.environ.get("DUAL_DISPLAY_FAKE_SECONDARY")
    if fake:
        try:
            l, t, w, h = (int(v.strip()) for v in fake.split(","))
            rect = (l, t, l + w, t + h)
            return Monitor(rect, rect, False), True
        except (ValueError, TypeError):
            pass
    monitors = get_monitors()
    if not monitors:
        rect = (0, 0, fallback_w, fallback_h)
        return Monitor(rect, rect, True), False
    extended = next((m for m in monitors if not m.primary), None)
    if extended:
        return extended, True
    primary = next((m for m in monitors if m.primary), monitors[0])
    return primary, False
