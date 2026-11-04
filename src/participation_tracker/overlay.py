"""Compact, non-activating, always-on-top selection overlay."""

from __future__ import annotations

import sys

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .monitors import GA_ROOT, Monitor, get_display_target
from .ui.theme import COLORS

_NAME_FONT_PX = 29
_MIN_NAME_FONT_PX = 12
_SCREEN_MARGIN = 24
# Same icons as the Picker page's action buttons, shown before the student's name.
_PICK_ICONS = {"random": "🎲", "teacher": "🍎", "volunteer": "🙋"}
_PICK_TIPS = {"random": "Picked randomly", "teacher": "Teacher pick", "volunteer": "Volunteered"}


class OverlayWindow(QWidget):
    def __init__(self, main_window: QWidget | None = None):
        super().__init__(None)
        self.main_window = main_window
        self.monitor_status = ""
        self.display_mode: str | None = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.frame = QFrame(self)
        self.frame.setStyleSheet(f"QFrame {{ background: {COLORS['overlay_bg']}; border: 1px solid #8B5CF6; border-radius: 3px; }} QLabel {{ color: {COLORS['overlay_fg']}; border: none; }}")
        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        self.student_content = QWidget(self.frame)
        student_row = QHBoxLayout(self.student_content)
        student_row.setContentsMargins(0, 0, 0, 0)
        student_row.setSpacing(10)
        self.badge = QLabel("🎲")
        self.badge.setStyleSheet("font-size: 23px;")
        self.name_label = QLabel("")
        self._set_name_font(_NAME_FONT_PX)
        student_row.addWidget(self.badge)
        student_row.addWidget(self.name_label)
        layout.addWidget(self.student_content)

        self.summary_content = QWidget(self.frame)
        summary_layout = QVBoxLayout(self.summary_content)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(10)
        self.summary_title = QLabel("Leaderboard")
        self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_title.setStyleSheet("font-size: 26px; font-weight: 700; color: white;")
        summary_layout.addWidget(self.summary_title)
        self.summary_table = QTableWidget(0, 6)
        self.summary_table.setHorizontalHeaderLabels(["Rank", "Name", "Picks", "Volunteers", "Total Points", "Score"])
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setWordWrap(False)
        self.summary_table.setSortingEnabled(False)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.summary_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, 6):
            self.summary_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.summary_table.setStyleSheet("""
            QTableWidget { background: #F8FAFC; alternate-background-color: #EEF2FF;
                color: #0F172A; border: 1px solid #C4B5FD; border-radius: 8px;
                gridline-color: #DDD6FE; font-size: 19px; }
            QHeaderView::section { background: #EDE9FE; color: #312E81; padding: 9px 12px;
                border: 0; border-bottom: 1px solid #C4B5FD; font-weight: 700; font-size: 18px; }
        """)
        summary_layout.addWidget(self.summary_table)
        layout.addWidget(self.summary_content)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.addWidget(self.frame)
        self.badge.hide()
        self.summary_content.hide()
        self.hide()

    def _set_name_font(self, size: int) -> None:
        self.name_label.setStyleSheet(f"font-size: {size}px; font-weight: 700;")

    def _content_size(self) -> QSize:
        """Exact box size for the text currently in the name label.

        The frame's hint is up to date as soon as the label text changes, while
        the window's own ``sizeHint()`` only catches up on the next layout pass:
        reading it right after ``setText`` sized the box for the *previous* name,
        which clipped every longer name.
        """
        hint = self.frame.sizeHint()
        margins = self.layout().contentsMargins()
        return QSize(
            hint.width() + margins.left() + margins.right(),
            hint.height() + margins.top() + margins.bottom(),
        )

    def _fit_name(self, available_width: int) -> QSize:
        """Box size for the current name, shrinking the font if the display is too narrow."""
        self._set_name_font(_NAME_FONT_PX)
        size = self._content_size()
        text_width = self.name_label.sizeHint().width()
        if size.width() <= available_width or text_width <= 0:
            return size
        # Keep the whole name readable rather than letting it run off the screen.
        chrome = size.width() - text_width
        scaled = int(_NAME_FONT_PX * max(0, available_width - chrome) / text_width)
        self._set_name_font(max(_MIN_NAME_FONT_PX, scaled))
        return self._content_size()

    def _target_ratio(self, monitor: Monitor) -> float:
        """Device pixel ratio of the display owning ``monitor`` (Win32 rects are physical)."""
        rect = QRect(monitor.rect[0], monitor.rect[1], monitor.rect[2] - monitor.rect[0], monitor.rect[3] - monitor.rect[1])
        best_ratio, best_area = 0.0, 0
        for screen in QGuiApplication.screens():
            ratio = screen.devicePixelRatio()
            geometry = screen.geometry()
            physical = QRect(
                round(geometry.x() * ratio), round(geometry.y() * ratio),
                round(geometry.width() * ratio), round(geometry.height() * ratio),
            )
            overlap = physical.intersected(rect)
            area = max(0, overlap.width()) * max(0, overlap.height())
            if area > best_area:
                best_ratio, best_area = ratio, area
        # No Qt screen matches (emulated or unusual setup): trust the window itself.
        return best_ratio or self.devicePixelRatioF()

    def show_student(self, name: str, kind: str = "random") -> str:
        """Show the student on the display, with the icon of the button that picked them."""
        self.display_mode = "student"
        self.name_label.setText(name)
        self.student_content.show()
        self.summary_content.hide()
        self.badge.setText(_PICK_ICONS.get(kind, _PICK_ICONS["random"]))
        self.badge.setToolTip(_PICK_TIPS.get(kind, _PICK_TIPS["random"]))
        self.badge.setVisible(True)
        fallback = self.screen().geometry() if self.screen() else None
        fw, fh = (fallback.width(), fallback.height()) if fallback else (1920, 1080)
        monitor, extended = get_display_target(fw, fh)
        left, top, right, bottom = monitor.work
        # Win32 reports the display in physical pixels; Qt sizes are logical.
        ratio = self._target_ratio(monitor)
        size = self._fit_name(int(max(160, (right - left - 2 * _SCREEN_MARGIN) / ratio)))
        width, height = size.width(), size.height()
        x = left + _SCREEN_MARGIN
        if x + width * ratio > right - _SCREEN_MARGIN:
            x = max(left, int(right - _SCREEN_MARGIN - width * ratio))
        y = max(top + _SCREEN_MARGIN, int(bottom - height * ratio - _SCREEN_MARGIN))
        self.setGeometry(x, y, width, height)
        self.show()
        self.raise_()
        self.monitor_status = "Showing on extended display" if extended else "No extended display — showing here"
        QTimer.singleShot(30, lambda: self._force_position(x, y, width, height, ratio))
        QTimer.singleShot(60, self._restore_focus)
        return self.monitor_status

    def show_leaderboard_summary(self, class_name: str, rows: list[tuple[str, str, str, str, str, str]]) -> str:
        """Show a centered leaderboard summary on the extended display.

        ``rows`` contain rank, student name, picks, volunteers, total participation
        points, and score.
        """
        self.display_mode = "leaderboard"
        self.student_content.hide()
        self.badge.hide()
        self.summary_content.show()
        self.summary_title.setText(f"Leaderboard — {class_name}")
        table = self.summary_table
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        row_height = 40
        table.verticalHeader().setDefaultSectionSize(row_height)

        fallback = self.screen().geometry() if self.screen() else None
        fw, fh = (fallback.width(), fallback.height()) if fallback else (1920, 1080)
        monitor, extended = get_display_target(fw, fh)
        left, top, right, bottom = monitor.work
        ratio = self._target_ratio(monitor)
        available_width = max(320, int((right - left - 2 * _SCREEN_MARGIN) / ratio))
        available_height = max(240, int((bottom - top - 2 * _SCREEN_MARGIN) / ratio))
        width = min(1200, available_width)
        visible_rows = min(max(len(rows), 4), 16)
        # Include the header and table frame so every visible row fits without
        # a scrollbar or a clipped final row.
        table_chrome = table.horizontalHeader().height() + 2 * table.frameWidth()
        table_height = min(available_height - 120, table_chrome + visible_rows * row_height)
        table.setFixedHeight(max(120, table_height))
        # The overlay is hidden while switching classes, and a hidden window
        # does not run a layout pass. Its size hint can therefore still describe
        # the previous class's table height, leaving the larger class clipped.
        # Compute the required height from the table and layout chrome instead.
        outer_margins = self.layout().contentsMargins()
        frame_margins = self.frame.layout().contentsMargins()
        summary_layout = self.summary_content.layout()
        summary_margins = summary_layout.contentsMargins()
        height = min(
            outer_margins.top() + outer_margins.bottom()
            + frame_margins.top() + frame_margins.bottom()
            + summary_margins.top() + summary_margins.bottom()
            + self.summary_title.sizeHint().height()
            + summary_layout.spacing()
            + table.height(),
            available_height,
        )
        x = int(left + ((right - left) - width * ratio) / 2)
        y = int(top + ((bottom - top) - height * ratio) / 2)
        self.setGeometry(x, y, width, height)
        self.show()
        self.raise_()
        self.monitor_status = "Showing leaderboard on extended display" if extended else "No extended display — showing here"
        QTimer.singleShot(30, lambda: self._force_position(x, y, width, height, ratio))
        QTimer.singleShot(60, self._restore_focus)
        return self.monitor_status

    def _force_position(self, x: int, y: int, width: int, height: int, ratio: float) -> None:
        if sys.platform != "win32":
            return
        try:
            user32 = __import__("ctypes").windll.user32
            hwnd = user32.GetAncestor(int(self.winId()), GA_ROOT)
            if hwnd:
                # MoveWindow takes physical pixels; passing the logical size made the
                # box smaller than its text on scaled displays and clipped the name.
                user32.MoveWindow(hwnd, x, y, round(width * ratio), round(height * ratio), True)
        except (AttributeError, OSError):
            pass

    def _restore_focus(self) -> None:
        if self.main_window is not None:
            self.main_window.activateWindow()
            self.main_window.raise_()

    def hide_overlay(self) -> None:
        self.display_mode = None
        self.hide()
