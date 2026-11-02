"""Regression tests for leaderboard cell sorting."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from participation_tracker.ui.main_window import _SortableItem


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_leaderboard_name_sort_is_case_insensitive_without_recursion(qapp):
    table = QTableWidget(3, 1)
    for row, name in enumerate(("Zoe Adams", "Alexandra Montgomery", "Benjamin Carter")):
        table.setItem(row, 0, _SortableItem(name))

    table.setSortingEnabled(True)
    table.sortItems(0)

    assert [table.item(row, 0).text() for row in range(3)] == [
        "Alexandra Montgomery", "Benjamin Carter", "Zoe Adams"
    ]

    table.sortItems(0, Qt.SortOrder.DescendingOrder)
    assert [table.item(row, 0).text() for row in range(3)] == [
        "Zoe Adams", "Benjamin Carter", "Alexandra Montgomery"
    ]


def test_leaderboard_numeric_sort_uses_numeric_values(qapp):
    table = QTableWidget(3, 1)
    for row, (text, value) in enumerate((("11", 11), ("2", 2), ("100", 100))):
        table.setItem(row, 0, _SortableItem(text, value))

    table.setSortingEnabled(True)
    table.sortItems(0)

    assert [table.item(row, 0).text() for row in range(3)] == ["2", "11", "100"]
