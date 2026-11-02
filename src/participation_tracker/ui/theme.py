"""Slate light theme tokens and application-wide Qt stylesheet."""

import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QPolygon

COLORS = {
    "bg": "#F8FAFC", "surface": "#FFFFFF", "surface_alt": "#F1F5F9", "border": "#E2E8F0",
    "text": "#0F172A", "text_muted": "#64748B", "accent": "#4F46E5", "accent_hover": "#4338CA",
    "accent_soft": "#EEF2FF", "success": "#10B981", "danger": "#EF4444", "warning": "#F59E0B",
    "info": "#0EA5E9", "overlay_bg": "#6D28D9", "overlay_fg": "#F8FAFC",
}
FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", sans-serif'


def _spin_arrow_url(up: bool) -> str:
    """Triangle image for the spin-box buttons.

    Qt's stylesheet engine drops the native arrows as soon as the up/down button
    sub-controls are styled, so the arrows are supplied as small generated PNGs.
    """
    folder = Path(tempfile.gettempdir()) / "participation_tracker_ui"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ("spin_up.png" if up else "spin_down.png")
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#047857" if up else "#B91C1C"))
    points = (QPoint(4, 10), QPoint(12, 10), QPoint(8, 4)) if up else (QPoint(4, 6), QPoint(12, 6), QPoint(8, 12))
    painter.drawPolygon(QPolygon(points))
    painter.end()
    pixmap.save(str(path))
    return path.as_posix()


def build_stylesheet() -> str:
    spin_up, spin_down = _spin_arrow_url(True), _spin_arrow_url(False)
    return f"""
* {{ font-family: {FONT_FAMILY}; color: {COLORS['text']}; }}
QMainWindow, QWidget#Root {{ background: {COLORS['bg']}; }}
QFrame#Sidebar {{ background: #111827; border: none; }}
QLabel#Brand {{ color: white; font-size: 18px; font-weight: 700; }}
QLabel#Subtle {{ color: {COLORS['text_muted']}; }}
QLabel#PageTitle {{ font-size: 25px; font-weight: 700; }}
QLabel#SectionTitle {{ font-size: 16px; font-weight: 650; }}
QFrame#Card {{ background: white; border: 1px solid {COLORS['border']}; border-radius: 12px; }}
QWidget#Panel {{ background: {COLORS['surface_alt']}; border-radius: 8px; }}
QPushButton {{ background: white; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 9px 14px; font-weight: 600; }}
QPushButton:hover {{ background: {COLORS['accent_soft']}; border-color: #C7D2FE; }}
QPushButton:pressed {{ background: #E0E7FF; }}
QPushButton:disabled {{ color: #94A3B8; background: #F1F5F9; }}
QPushButton[variant="primary"] {{ background: {COLORS['accent']}; color: white; border: 0; }}
QPushButton[variant="primary"]:hover {{ background: {COLORS['accent_hover']}; }}
QPushButton[variant="success"] {{ background: {COLORS['success']}; color: white; border: 0; }}
QPushButton[variant="danger"] {{ background: {COLORS['danger']}; color: white; border: 0; }}
QPushButton[variant="warning"] {{ background: {COLORS['warning']}; color: white; border: 0; }}
QPushButton[variant="info"] {{ background: {COLORS['info']}; color: white; border: 0; }}
QPushButton[nav="true"] {{ text-align: left; color: #CBD5E1; background: transparent; border: 0; padding: 12px; }}
QPushButton[nav="true"]:hover {{ color: white; background: #1F2937; }}
QPushButton[navCompact="true"] {{ text-align: center; padding: 10px 0; }}
QPushButton[navActive="true"] {{ color: white; background: #3730A3; }}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: white; border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 8px; selection-background-color: {COLORS['accent']}; }}
QComboBox[flag="positive"] {{ color: #047857; background: #D1FAE5; border-color: #6EE7B7; font-weight: 600; }}
QComboBox[flag="caution"] {{ color: #B45309; background: #FEF3C7; border-color: #FCD34D; font-weight: 600; }}
QComboBox[flag="negative"] {{ color: #B91C1C; background: #FEE2E2; border-color: #FCA5A5; font-weight: 600; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 22px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 18px; background: #D1FAE5; border: 0; border-left: 1px solid {COLORS['border']}; border-top-right-radius: 6px; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{ background: #A7F3D0; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 18px; background: #FEE2E2; border: 0; border-left: 1px solid {COLORS['border']}; border-bottom-right-radius: 6px; }}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: #FECACA; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{spin_up}"); width: 8px; height: 8px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{spin_down}"); width: 8px; height: 8px; }}
QTableWidget, QTreeWidget {{ background: white; border: 1px solid {COLORS['border']}; border-radius: 8px; gridline-color: {COLORS['border']}; alternate-background-color: #F8FAFC; }}
QHeaderView::section {{ background: #F1F5F9; padding: 9px; border: 0; border-bottom: 1px solid {COLORS['border']}; font-weight: 700; }}
QCheckBox {{ spacing: 8px; }}
QScrollArea {{ border: none; background: transparent; }}
QStatusBar {{ background: white; color: {COLORS['text_muted']}; border-top: 1px solid {COLORS['border']}; }}
"""


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
