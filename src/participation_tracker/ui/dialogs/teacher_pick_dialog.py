"""Searchable student chooser used by Teacher Pick and Volunteer.

Mirrors the web v2 ``StudentPickModal``: present students first, absent students
grouped and dimmed for teacher picks, per-student session counters, and a
``last`` marker on the most recently picked student.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

_COUNTERS = ("picks", "correct", "incorrect", "volunteers", "skips")
_EMPTY = {field: 0 for field in _COUNTERS}


def _stats_line(stats: dict | None) -> str:
    stats = stats or _EMPTY
    values = {field: int(stats.get(field, 0) or 0) for field in _COUNTERS}
    return (
        f"Session · Picks {values['picks']} · ✓{values['correct']} · "
        f"✗{values['incorrect']} · 🙋{values['volunteers']} · ⏭{values['skips']}"
    )


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
        self.resize(480, 540)
        self.selected_name: str | None = None
        self._mode = mode
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search students…")
        self._searchable = searchable
        self.search.setVisible(searchable)
        layout.addWidget(self.search)
        self.list = QListWidget()
        layout.addWidget(self.list)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        choose = QPushButton("Select student")
        choose.setProperty("variant", "primary")
        choose.clicked.connect(self._select)
        buttons.addWidget(cancel)
        buttons.addWidget(choose)
        layout.addLayout(buttons)
        self.names = names
        self.present = present
        self.session_stats = session_stats or {}
        self.last_picked = last_picked
        self.search.textChanged.connect(self._populate)
        self.list.itemDoubleClicked.connect(lambda _item: self._select())
        self._populate()

    def _add_group(self, label: str):
        header = QListWidgetItem(label)
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        font = QFont()
        font.setBold(True)
        header.setFont(font)
        self.list.addItem(header)

    def _add_student(self, name: str, absent: bool):
        badge = "  (last)" if name == self.last_picked else ""
        item = QListWidgetItem(f"{name}{badge}\n    {_stats_line(self.session_stats.get(name))}")
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setToolTip(_stats_line(self.session_stats.get(name)))
        if absent:
            font = item.font()
            font.setItalic(True)
            item.setFont(font)
            item.setForeground(Qt.GlobalColor.gray)
        self.list.addItem(item)

    def _populate(self):
        query = self.search.text().casefold()
        self.list.clear()
        if self._mode == "volunteer":
            groups = [("", [n for n in self.names if n in self.present])]
        else:
            groups = [
                ("Present", [n for n in self.names if n in self.present]),
                ("Absent", [n for n in self.names if n not in self.present]),
            ]
        multiple_groups = len(groups) > 1
        for label, names in groups:
            filtered = [n for n in names if query in n.casefold()]
            if not filtered:
                continue
            if label and multiple_groups:
                self._add_group(label)
            for name in filtered:
                self._add_student(name, absent=label == "Absent")

    @property
    def searchable(self):
        return self._searchable

    def _select(self):
        item = self.list.currentItem()
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return
        name = item.data(Qt.ItemDataRole.UserRole)
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
