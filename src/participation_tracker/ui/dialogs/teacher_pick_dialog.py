"""Searchable student chooser used by Teacher Pick and Volunteer.

Mirrors the web v2 ``StudentPickModal``: present students first, absent students
grouped and dimmed for teacher picks, per-student session counters laid out in
aligned columns, and a ``last`` marker on the most recently picked student.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

_COUNTERS = ("picks", "correct", "incorrect", "volunteers", "skips")
_EMPTY = {field: 0 for field in _COUNTERS}
# One column per session counter, in the order the picker records results.
_COLUMNS = (
    ("Picks", "picks"),
    ("Correct", "correct"),
    ("Incorrect", "incorrect"),
    ("Volunteers", "volunteers"),
    ("Skips", "skips"),
)
_ABSENT_COLOR = QColor("#94A3B8")
_GROUP_BG = QColor("#E2E8F0")


def _counters(stats: dict | None) -> dict[str, int]:
    stats = stats or _EMPTY
    return {field: int(stats.get(field, 0) or 0) for field in _COUNTERS}


class StudentPickDialog(QDialog):
    def __init__(
        self,
        names: list[str],
        present: set[str],
        title: str,
        searchable: bool = True,
        parent=None,
        *,
        session_stats: dict | None = None,
        last_picked: str | None = None,
        mode: str = "teacher",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(660, 560)
        self.selected_name: str | None = None
        self._mode = mode
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search students…")
        self._searchable = searchable
        self.search.setVisible(searchable)
        layout.addWidget(self.search)
        hint = QLabel("Session tallies")
        hint.setObjectName("Subtle")
        layout.addWidget(hint)
        self.list = self._build_table()
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        choose = QPushButton("Select student")
        choose.setProperty("variant", "primary")
        choose.setDefault(True)
        choose.clicked.connect(self._select)
        buttons.addWidget(cancel)
        buttons.addWidget(choose)
        layout.addLayout(buttons)
        self.names = names
        self.present = present
        self.session_stats = session_stats or {}
        self.last_picked = last_picked
        self.search.textChanged.connect(self._populate)
        self.list.itemDoubleClicked.connect(lambda *_args: self._select())
        self._populate()

    def _build_table(self) -> QTreeWidget:
        """One row per student, one column per session counter."""
        table = QTreeWidget()
        table.setColumnCount(1 + len(_COLUMNS))
        table.setHeaderLabels(["Student"] + [label for label, _field in _COLUMNS])
        table.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        table.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        table.setUniformRowHeights(True)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        header = table.header()
        header.setStretchLastSection(False)
        header.setStyleSheet("QHeaderView::section { padding: 4px 6px; }")
        for column in range(table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        return table

    def _add_group(self, label: str, count: int) -> QTreeWidgetItem:
        group = QTreeWidgetItem([f"{label} ({count})"])
        group.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = QFont()
        font.setBold(True)
        group.setFont(0, font)
        group.setBackground(0, _GROUP_BG)
        self.list.addTopLevelItem(group)
        # Spanning only takes effect once the row belongs to the tree.
        group.setFirstColumnSpanned(True)
        group.setExpanded(True)
        return group

    def _add_student(self, parent: QTreeWidgetItem | None, name: str, absent: bool) -> QTreeWidgetItem:
        values = _counters(self.session_stats.get(name))
        badge = "  (last)" if name == self.last_picked else ""
        item = QTreeWidgetItem([f"{name}{badge}"] + [str(values[field]) for _label, field in _COLUMNS])
        item.setData(0, Qt.ItemDataRole.UserRole, name)
        item.setToolTip(0, name)
        for column in range(1, self.list.columnCount()):
            item.setTextAlignment(column, Qt.AlignmentFlag.AlignCenter)
        if absent:
            font = QFont()
            font.setItalic(True)
            for column in range(self.list.columnCount()):
                item.setFont(column, font)
                item.setForeground(column, _ABSENT_COLOR)
        if parent is None:
            self.list.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def _populate(self):
        query = self.search.text().casefold()
        self.list.clear()
        if self._mode == "volunteer":
            groups = [(None, [n for n in self.names if n in self.present])]
        else:
            groups = [
                ("Present", [n for n in self.names if n in self.present]),
                ("Absent", [n for n in self.names if n not in self.present]),
            ]
        multiple_groups = len(groups) > 1
        self.list.setRootIsDecorated(multiple_groups)
        first_match: QTreeWidgetItem | None = None
        for label, names in groups:
            filtered = [n for n in names if query in n.casefold()]
            if not filtered:
                continue
            parent = None
            if label and multiple_groups:
                parent = self._add_group(label, len(filtered))
            for name in filtered:
                item = self._add_student(parent, name, absent=label == "Absent")
                if first_match is None:
                    first_match = item
        if query and first_match is not None:
            # Highlight the best match so Enter selects it straight away.
            self.list.setCurrentItem(first_match)

    @property
    def searchable(self):
        return self._searchable

    def _select(self):
        item = self.list.currentItem()
        if item is None:
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if name:
            self.selected_name = name
            self.accept()


class ImportModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import data")
        self.resize(440, 200)
        self.mode = "merge"
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose how imported student records should be applied."))
        layout.addWidget(QLabel("Merge adds missing classes/students and overwrites counters for matching students."))
        row = QHBoxLayout()
        replace = QPushButton("Replace all data")
        replace.setProperty("variant", "danger")
        replace.clicked.connect(lambda: self._choose("replace"))
        merge = QPushButton("Merge data")
        merge.setProperty("variant", "primary")
        merge.clicked.connect(lambda: self._choose("merge"))
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(replace)
        row.addWidget(merge)
        row.addWidget(cancel)
        layout.addLayout(row)

    def _choose(self, mode):
        self.mode = mode
        self.accept()
