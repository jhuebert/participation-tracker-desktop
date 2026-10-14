"""Slate light theme tokens and application-wide Qt stylesheet."""

COLORS = {
    "bg": "#F8FAFC", "surface": "#FFFFFF", "surface_alt": "#F1F5F9", "border": "#E2E8F0",
    "text": "#0F172A", "text_muted": "#64748B", "accent": "#4F46E5", "accent_hover": "#4338CA",
    "accent_soft": "#EEF2FF", "success": "#10B981", "danger": "#EF4444", "warning": "#F59E0B",
    "info": "#0EA5E9", "overlay_bg": "#6D28D9", "overlay_fg": "#F8FAFC",
}
FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", sans-serif'

QSS = f"""
* {{ font-family: {FONT_FAMILY}; color: {COLORS['text']}; }}
QMainWindow, QWidget#Root {{ background: {COLORS['bg']}; }}
QFrame#Sidebar {{ background: #111827; border: none; }}
QLabel#Brand {{ color: white; font-size: 18px; font-weight: 700; }}
QLabel#Subtle {{ color: {COLORS['text_muted']}; }}
QLabel#PageTitle {{ font-size: 25px; font-weight: 700; }}
QLabel#SectionTitle {{ font-size: 16px; font-weight: 650; }}
QFrame#Card {{ background: white; border: 1px solid {COLORS['border']}; border-radius: 12px; }}
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
QPushButton[navActive="true"] {{ color: white; background: #3730A3; }}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: white; border: 1px solid {COLORS['border']}; border-radius: 7px; padding: 8px; selection-background-color: {COLORS['accent']}; }}
QTableWidget {{ background: white; border: 1px solid {COLORS['border']}; border-radius: 8px; gridline-color: {COLORS['border']}; alternate-background-color: #F8FAFC; }}
QHeaderView::section {{ background: #F1F5F9; padding: 9px; border: 0; border-bottom: 1px solid {COLORS['border']}; font-weight: 700; }}
QCheckBox {{ spacing: 8px; }}
QScrollArea {{ border: none; background: transparent; }}
QStatusBar {{ background: white; color: {COLORS['text_muted']}; border-top: 1px solid {COLORS['border']}; }}
"""


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
