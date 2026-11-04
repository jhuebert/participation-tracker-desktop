"""Regression tests for second-monitor leaderboard contents."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from participation_tracker.overlay import OverlayWindow
from participation_tracker.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _summary_rows(count: int) -> list[tuple[str, str, str, str, str, str]]:
    return [
        (str(rank), f"Student {rank}", "0", "0", "0.00", "0.00")
        for rank in range(1, count + 1)
    ]


def test_overlay_rows_use_selected_class_not_stale_table_count(qapp, repo):
    previous_class = repo.create_class("Previous", [f"Previous {i}" for i in range(5)])
    selected_names = [f"Student {i}" for i in range(12)]
    selected_class = repo.create_class("Selected", selected_names)
    repo.apply_event(selected_class.id, selected_names[0], "picks")
    repo.apply_event(selected_class.id, selected_names[0], "volunteers")
    window = MainWindow(repo)
    try:
        window._load_class(previous_class.id)
        window._load_class(selected_class.id)

        # Simulate the presentation table still having the prior class's size.
        window.leaderboard_table.setRowCount(5)

        rows = window._leaderboard_summary_rows()

        assert len(rows) == len(selected_names)
        assert {row[1] for row in rows} == set(selected_names)
        assert all(len(row) == 6 for row in rows)
        first_student = next(row for row in rows if row[1] == selected_names[0])
        assert first_student[2:4] == ("1", "1")
        assert window.overlay.summary_table.columnCount() == 6
        assert [
            window.overlay.summary_table.horizontalHeaderItem(column).text()
            for column in range(6)
        ] == ["Rank", "Name", "Picks", "Volunteers", "Total Points", "Score"]
    finally:
        window.overlay.close()
        window.close()


def test_overlay_grows_after_hidden_switch_to_larger_class(qapp, monkeypatch):
    monkeypatch.setenv("DUAL_DISPLAY_FAKE_SECONDARY", "5000,0,1920,1080")
    overlay = OverlayWindow()
    try:
        overlay.show_leaderboard_summary("Small", _summary_rows(5))
        qapp.processEvents()
        small_height = overlay.height()

        # _load_class hides the overlay before refreshing it for the new class.
        overlay.hide()
        overlay.show_leaderboard_summary("Large", _summary_rows(12))
        qapp.processEvents()

        table = overlay.summary_table
        assert table.rowCount() == 12
        assert overlay.height() > small_height
        assert overlay.height() >= table.height()
        assert not table.verticalScrollBar().isVisible()
    finally:
        overlay.close()
