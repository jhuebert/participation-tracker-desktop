"""Non-modal status toast helper."""

from PySide6.QtCore import QTimer


def show_toast(status_bar, message: str, timeout: int = 3000) -> None:
    status_bar.showMessage(message, timeout)
