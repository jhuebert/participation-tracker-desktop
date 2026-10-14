"""Compact, non-activating, always-on-top selection overlay."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from .monitors import GA_ROOT, get_display_target
from .ui.theme import COLORS


class OverlayWindow(QWidget):
    def __init__(self, main_window: QWidget | None = None):
        super().__init__(None)
        self.main_window = main_window
        self.monitor_status = ""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        frame = QFrame(self)
        frame.setStyleSheet(f"QFrame {{ background: {COLORS['overlay_bg']}; border: 1px solid #8B5CF6; border-radius: 3px; }} QLabel {{ color: {COLORS['overlay_fg']}; border: none; }}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(10)
        self.volunteer = QLabel("🙋")
        self.volunteer.setStyleSheet("font-size: 23px;")
        self.name_label = QLabel("")
        self.name_label.setStyleSheet("font-size: 29px; font-weight: 700;")
        layout.addWidget(self.volunteer)
        layout.addWidget(self.name_label)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.addWidget(frame)
        self.volunteer.hide()
        self.hide()

    def show_student(self, name: str, is_volunteer: bool = False) -> str:
        self.name_label.setText(name)
        self.volunteer.setVisible(is_volunteer)
        self.adjustSize()
        fallback = self.screen().geometry() if self.screen() else None
        fw, fh = (fallback.width(), fallback.height()) if fallback else (1920, 1080)
        monitor, extended = get_display_target(fw, fh)
        left, top, right, bottom = monitor.work
        width, height = self.sizeHint().width(), self.sizeHint().height()
        x = left + 24
        y = max(top + 24, bottom - height - 24)
        self.setGeometry(x, y, width, height)
        self.show()
        self.raise_()
        self.monitor_status = "Showing on extended display" if extended else "No extended display — showing here"
        QTimer.singleShot(30, lambda: self._force_position(x, y, width, height))
        QTimer.singleShot(60, self._restore_focus)
        return self.monitor_status

    def _force_position(self, x: int, y: int, width: int, height: int) -> None:
        if sys.platform != "win32":
            return
        try:
            user32 = __import__("ctypes").windll.user32
            hwnd = user32.GetAncestor(int(self.winId()), GA_ROOT)
            if hwnd:
                user32.MoveWindow(hwnd, x, y, width, height, True)
        except (AttributeError, OSError):
            pass

    def _restore_focus(self) -> None:
        if self.main_window is not None:
            self.main_window.activateWindow()
            self.main_window.raise_()

    def hide_overlay(self) -> None:
        self.hide()
