"""Edit a class: rename it and add / rename / remove its students.

Mirrors the web v2 Manage "Edit class" modal. Edits are applied to the
repository immediately; the dialog only needs to be dismissed afterwards.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ClassEditDialog(QDialog):
    def __init__(self, repository, klass, parent=None, session=None):
        super().__init__(parent)
        self.repo = repository
        self.session = session  # live session, when editing the current class
        self.class_id = klass.id
        self.class_name = klass.name
        self.setWindowTitle(f"Edit {klass.name}")
        self.resize(560, 600)
        self._build()
        self._reload()

    # ------------------------------------------------------------------ build
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(self._section("Class name"))
        rename_row = QHBoxLayout()
        self.name_edit = QLineEdit(self.class_name)
        rename_row.addWidget(self.name_edit, 1)
        rename_row.addWidget(self._button("Rename", "primary", self._rename_class))
        layout.addLayout(rename_row)

        layout.addWidget(self._section("Students"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._students_host = QWidget()
        self._students_layout = QVBoxLayout(self._students_host)
        self._students_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._students_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._students_host)
        layout.addWidget(scroll, 1)

        layout.addWidget(self._section("Add student"))
        add_row = QHBoxLayout()
        self.new_student = QLineEdit()
        self.new_student.setPlaceholderText("Student name")
        self.new_student.returnPressed.connect(self._add_student)
        add_row.addWidget(self.new_student, 1)
        add_row.addWidget(self._button("Add", "primary", self._add_student))
        layout.addLayout(add_row)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self._button("Close", "", self.accept))
        layout.addLayout(footer)

    def _section(self, text):
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _button(self, text, variant, callback):
        button = QPushButton(text)
        if variant:
            button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    # --------------------------------------------------------------- rendering
    def _reload(self):
        while self._students_layout.count():
            item = self._students_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        students = self.repo.list_students(self.class_id)
        if not students:
            self._students_layout.addWidget(QLabel("No students yet."))
            return
        for student in students:
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            editor = QLineEdit(student.name)
            editor.setToolTip("Rename this student")
            hl.addWidget(editor, 1)
            hl.addWidget(
                self._button("Save", "", lambda _=False, e=editor, s=student: self._rename_student(s.name, e.text()))
            )
            hl.addWidget(
                self._button("Remove", "danger", lambda _=False, s=student: self._remove_student(s.name))
            )
            self._students_layout.addWidget(row)

    # ---------------------------------------------------------------- actions
    def _rename_class(self):
        new_name = self.name_edit.text().strip()
        if new_name == self.class_name:
            return
        try:
            self.repo.rename_class(self.class_id, new_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Rename class", str(exc))
            self.name_edit.setText(self.class_name)
            return
        self.class_name = new_name
        self.setWindowTitle(f"Edit {new_name}")

    def _add_student(self):
        name = self.new_student.text().strip()
        if not name:
            return
        try:
            self.repo.add_student(self.class_id, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Add student", str(exc))
            return
        if self.session:
            self.session.add_student(name)
        self.new_student.clear()
        self._reload()

    def _rename_student(self, current_name: str, new_name: str):
        if new_name.strip() == current_name:
            return
        try:
            self.repo.rename_student(self.class_id, current_name, new_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Rename student", str(exc))
            return
        if self.session:
            self.session.rename_student(current_name, new_name.strip())
        self._reload()

    def _remove_student(self, name: str):
        answer = QMessageBox.question(
            self,
            "Remove student",
            f'Remove "{name}" from {self.class_name}? Their stats will be lost.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.repo.remove_student(self.class_id, name)
        if self.session:
            self.session.remove_student(name)
        self._reload()
