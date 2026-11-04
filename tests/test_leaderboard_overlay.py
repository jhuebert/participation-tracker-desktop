"""Regression tests for second-monitor leaderboard contents."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from participation_tracker.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


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
