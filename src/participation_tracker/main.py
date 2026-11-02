"""Application bootstrap."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from participation_tracker import config
from participation_tracker.db.database import Database
from participation_tracker.db.repository import Repository
from participation_tracker.logging_setup import install_excepthook, setup_logging
from participation_tracker.ui.main_window import MainWindow
from participation_tracker.ui.theme import apply_theme


def main() -> int:
    setup_logging()
    log = logging.getLogger(__name__)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName("ParticipationTracker")
    icon_path = (
        Path(sys._MEIPASS) / "assets" / "icon.ico"
        if getattr(sys, "frozen", False)
        else config.app_dir() / "assets" / "icon.ico"
    )
    app_icon = QIcon(str(icon_path))
    app.setWindowIcon(app_icon)
    apply_theme(app)

    def show_uncaught(exc):
        QMessageBox.critical(None, "Unexpected error", f"An unexpected error occurred. Details are in the log file.\n\n{exc}")

    install_excepthook(show_uncaught)
    database = None
    try:
        data_folder = config.data_dir()
        fallback = data_folder != config.app_dir()
        database = Database(config.db_path())
        database.initialize()
        window = MainWindow(Repository(database), fallback_data_dir=fallback)
        window.show()
        result = app.exec()
        database.close()
        return result
    except Exception as exc:
        log.exception("Application failed to start")
        QMessageBox.critical(None, "Participation Tracker", f"Could not start the application.\n\n{exc}")
        if database:
            database.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
