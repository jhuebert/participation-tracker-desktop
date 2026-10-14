"""Main application window and four functional tracker pages."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QDoubleSpinBox, QStackedWidget,
    QStatusBar, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from ..db.repository import Repository
from ..models import COUNTER_FIELDS, Class, Settings, Student
from ..overlay import OverlayWindow
from ..services.exporter import export_backup, export_csv
from ..services.importer import (
    ImportError,
    extract_backup_settings,
    parse_backup_json,
    parse_class_csv,
)
from ..services.picker import pick_random
from ..services.scoring import leaderboard_score, participation_points
from ..services.session import Session
from .dialogs.class_edit_dialog import ClassEditDialog
from .dialogs.teacher_pick_dialog import ImportModeDialog, StudentPickDialog
from .theme import COLORS
from .widgets.stat_card import StatCard

log = logging.getLogger(__name__)


class _SortableItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: float | None = None):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if self.sort_value is not None and isinstance(other, _SortableItem) and other.sort_value is not None:
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class MainWindow(QMainWindow):
    def __init__(self, repository: Repository, fallback_data_dir: bool = False):
        super().__init__()
        self.repo = repository
        self.settings = repository.get_settings()
        self.session = Session()
        self.current_class: Class | None = None
        self.students: dict[str, Student] = {}
        self.volunteer_current = False
        self.overlay = OverlayWindow(self)
        self._building_attendance = False
        self.setWindowTitle("Participation Tracker")
        self.resize(1250, 850)
        self.setMinimumSize(970, 650)
        self._build_ui()
        self._build_menu()
        self._refresh_class_lists()
        self._set_page(0)
        self._update_header()
        self._refresh_class_list()
        self._shortcut_setup()
        if fallback_data_dir:
            QTimer.singleShot(500, lambda: self.toast("Data folder is read-only; using Local AppData instead.", "info"))

    # ---------------------------------------------------------------- layout
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 24, 16, 18)
        brand = QLabel("🎯  Participation\n      Tracker")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        side.addSpacing(26)
        self.nav_buttons = []
        for i, (icon, label) in enumerate((("🎲", "Picker"), ("📊", "Leaderboard"), ("🍎", "Classes"), ("⚙️", "Settings"))):
            button = QPushButton(f"{icon}    {label}")
            button.setProperty("nav", "true")
            button.clicked.connect(lambda _checked=False, idx=i: self._set_page(idx))
            side.addWidget(button)
            self.nav_buttons.append(button)
        side.addStretch(1)
        self.overlay_toggle = QCheckBox("Second monitor overlay")
        self.overlay_toggle.setStyleSheet("color: #CBD5E1; padding: 8px 2px;")
        self.overlay_toggle.setChecked(self.settings.overlay_enabled)
        self.overlay_toggle.toggled.connect(self._toggle_overlay)
        side.addWidget(self.overlay_toggle)
        outer.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 20, 28, 20)
        content_layout.setSpacing(16)
        header = QHBoxLayout()
        self.page_title = QLabel("Picker")
        self.page_title.setObjectName("PageTitle")
        header.addWidget(self.page_title)
        header.addStretch(1)
        header.addWidget(QLabel("Class"))
        self.class_selector = QComboBox()
        self.class_selector.setMinimumWidth(210)
        self.class_selector.currentIndexChanged.connect(self._header_class_changed)
        header.addWidget(self.class_selector)
        self.attendance_chip = QLabel("No class selected")
        self.attendance_chip.setStyleSheet("background:#EEF2FF;color:#4338CA;border-radius:14px;padding:7px 12px;font-weight:600;")
        header.addWidget(self.attendance_chip)
        self.overlay_chip = QLabel("Overlay off")
        self.overlay_chip.setStyleSheet("background:#F1F5F9;color:#64748B;border-radius:14px;padding:7px 12px;font-weight:600;")
        header.addWidget(self.overlay_chip)
        content_layout.addLayout(header)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        outer.addWidget(content, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())

        self.picker_page = self._build_picker_page()
        self.leaderboard_page = self._build_leaderboard_page()
        self.classes_page = self._build_classes_page()
        self.settings_page = self._build_settings_page()
        for page in (self.picker_page, self.leaderboard_page, self.classes_page, self.settings_page):
            self.stack.addWidget(page)

    def _section_title(self, text):
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _card(self, parent_layout, margins=(16, 14, 16, 14)):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(*margins)
        parent_layout.addWidget(frame)
        return frame, layout

    def _build_picker_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.stat_cards = {}
        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (key, title) in enumerate((("students", "Total Students"), ("present", "Present"), ("picks", "Total Picks"), ("correct", "Correct"), ("volunteers", "Volunteers"), ("skips", "Skips"))):
            card = StatCard(title)
            grid.addWidget(card, 0, i)
            self.stat_cards[key] = card
        layout.addLayout(grid)

        frame, card_layout = self._card(layout)
        card_layout.addWidget(self._section_title("Current selection"))
        self.selection_label = QLabel("Select a class to get started")
        self.selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_label.setMinimumHeight(105)
        self.selection_label.setStyleSheet("font-size:32px;font-weight:750;color:#4F46E5;background:#EEF2FF;border-radius:10px;")
        card_layout.addWidget(self.selection_label)
        buttons = QHBoxLayout()
        self.pick_button = self._button("🎲 Pick Random", "primary", self.pick_random)
        self.teacher_button = self._button("🍎 Teacher Pick", "info", self.teacher_pick)
        self.volunteer_button = self._button("🙋 Volunteer", "warning", self.volunteer_pick)
        for b in (self.pick_button, self.teacher_button, self.volunteer_button):
            buttons.addWidget(b)
        card_layout.addLayout(buttons)
        answer_buttons = QHBoxLayout()
        self.correct_button = self._button("✓ Correct", "success", lambda: self.mark_result("correct"))
        self.incorrect_button = self._button("✗ Incorrect", "danger", lambda: self.mark_result("incorrect"))
        self.skip_button = self._button("⏭ Skip", "", self.mark_skip)
        for b in (self.correct_button, self.incorrect_button, self.skip_button):
            answer_buttons.addWidget(b)
        card_layout.addLayout(answer_buttons)
        layout.addWidget(frame)

        frame, attendance = self._card(layout, (16, 12, 16, 12))
        top = QHBoxLayout()
        top.addWidget(self._section_title("Attendance"))
        top.addStretch(1)
        top.addWidget(self._button("🔄 Start new session", "info", self.start_new_session))
        top.addWidget(self._button("Reset session skips", "", self.reset_session_skips))
        top.addWidget(self._button("Select all", "", self.select_all))
        top.addWidget(self._button("Deselect all", "", self.deselect_all))
        attendance.addLayout(top)
        self.attendance_scroll = QScrollArea()
        self.attendance_scroll.setWidgetResizable(True)
        self.attendance_scroll.setMaximumHeight(220)
        self.attendance_widget = QWidget()
        self.attendance_grid = QGridLayout(self.attendance_widget)
        self.attendance_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.attendance_scroll.setWidget(self.attendance_widget)
        attendance.addWidget(self.attendance_scroll)
        layout.addWidget(frame, 1)
        self._enable_action_buttons(False)
        return page

    def _build_leaderboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        self.leaderboard_selector = QComboBox()
        self.leaderboard_selector.setMinimumWidth(230)
        self.leaderboard_selector.currentIndexChanged.connect(self._refresh_leaderboard)
        toolbar.addWidget(QLabel("Class"))
        toolbar.addWidget(self.leaderboard_selector)
        toolbar.addStretch(1)
        toolbar.addWidget(self._button("📊 Export CSV", "success", self.export_current_csv))
        toolbar.addWidget(self._button("🗑 Reset stats", "danger", self.reset_stats))
        layout.addLayout(toolbar)
        self.leaderboard_table = QTableWidget(0, 9)
        self.leaderboard_table.setHorizontalHeaderLabels(["Rank", "Name", "Picks", "Volunteers", "Skips", "Correct", "Incorrect", "Total Participation Points", "Leaderboard Score"])
        self.leaderboard_table.setAlternatingRowColors(True)
        self.leaderboard_table.setSortingEnabled(True)
        self.leaderboard_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.leaderboard_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.leaderboard_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.leaderboard_table)
        return page

    def _build_classes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form_card, form = self._card(layout)
        form.addWidget(self._section_title("Create a class"))
        self.new_class_name = QLineEdit()
        self.new_class_name.setPlaceholderText("Class name, e.g. Period 1 - Math")
        self.new_class_students = QTextEdit()
        self.new_class_students.setPlaceholderText("Student names, one per line")
        self.new_class_students.setMaximumHeight(130)
        form.addWidget(self.new_class_name)
        form.addWidget(self.new_class_students)
        row = QHBoxLayout()
        row.addWidget(self._button("Create class", "primary", self.create_class))
        row.addStretch(1)
        row.addWidget(self._button("📥 Import JSON / CSV", "info", self.import_file))
        row.addWidget(self._button("📤 Export backup", "", self.export_backup))
        form.addLayout(row)
        list_card, list_layout = self._card(layout)
        list_layout.addWidget(self._section_title("Your classes"))
        self.classes_list = QVBoxLayout()
        self.classes_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        list_layout.addLayout(self.classes_list)
        layout.addWidget(list_card, 1)
        return page

    def _build_settings_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        layout = QVBoxLayout(form_widget)
        frame, form = self._card(layout)
        form.addWidget(self._section_title("Session"))
        self.skip_limit = QSpinBox()
        self.skip_limit.setRange(0, 100)
        self.skip_limit.setValue(self.settings.skip_limit)
        skip_row = QHBoxLayout()
        skip_row.addWidget(QLabel("Skip limit per student (0 = unlimited)"))
        skip_row.addStretch(1)
        skip_row.addWidget(self.skip_limit)
        form.addLayout(skip_row)
        frame2, weighted = self._card(layout)
        self.weighted_enabled = QCheckBox("Enable fair weighted random selection")
        self.weighted_enabled.setChecked(self.settings.weighted_enabled)
        weighted.addWidget(self.weighted_enabled)
        self.weight_controls = {}
        for key, label, default_dir, amt in (
            ("volunteer", "Volunteer events", "decrease", 30),
            ("correct", "Correct answers", "decrease", 15),
            ("incorrect", "Incorrect answers", "increase", 10),
            ("skip", "Skips", "increase", 20),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            direction = QComboBox()
            direction.addItems(["decrease", "increase"])
            direction.setCurrentText(getattr(self.settings, f"weight_{key}_dir"))
            amount = QSpinBox()
            amount.setRange(0, 1000)
            amount.setValue(getattr(self.settings, f"weight_{key}_amt"))
            row.addWidget(direction)
            row.addWidget(QLabel("weight per event"))
            row.addWidget(amount)
            weighted.addLayout(row)
            self.weight_controls[key] = (direction, amount)
        frame3, scoring = self._card(layout)
        scoring.addWidget(self._section_title("Participation scoring"))
        self.scoring_controls = {}
        for key, label in (("correct", "Correct response"), ("volunteer", "Volunteer"), ("incorrect", "Incorrect response"), ("skip", "Skip")):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            effect = QComboBox()
            effect.addItems(["add", "subtract"])
            effect.setCurrentText(getattr(self.settings, f"scoring_{key}_effect"))
            points = QDoubleSpinBox()
            points.setRange(0, 1000)
            points.setSingleStep(0.5)
            points.setValue(getattr(self.settings, f"scoring_{key}_points"))
            row.addWidget(effect)
            row.addWidget(QLabel("points"))
            row.addWidget(points)
            scoring.addLayout(row)
            self.scoring_controls[key] = (effect, points)
        self.formula_preview = QLabel()
        self.formula_preview.setWordWrap(True)
        self.formula_preview.setStyleSheet("background:#EEF2FF;color:#3730A3;border-radius:8px;padding:10px;")
        scoring.addWidget(self.formula_preview)
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self._button("Save settings", "primary", self.save_settings))
        layout.addLayout(save_row)
        layout.addStretch(1)
        scroll.setWidget(form_widget)
        outer.addWidget(scroll)
        self._update_formula()
        for pair in self.scoring_controls.values():
            pair[0].currentTextChanged.connect(self._update_formula)
            pair[1].valueChanged.connect(self._update_formula)
        return page

    def _button(self, text, variant, callback):
        button = QPushButton(text)
        if variant:
            button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    # ---------------------------------------------------------------- events
    def _build_menu(self):
        file_menu = self.menuBar().addMenu("File")
        imp = QAction("Import…", self)
        imp.triggered.connect(self.import_file)
        exp = QAction("Export backup…", self)
        exp.triggered.connect(self.export_backup)
        file_menu.addAction(imp)
        file_menu.addAction(exp)

    def _shortcut_setup(self):
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.clear_selection)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.pick_random)
        for i in range(1, 5):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda idx=i - 1: self._set_page(idx))

    def _set_page(self, index: int):
        self.stack.setCurrentIndex(index)
        self.page_title.setText(["Picker", "Leaderboard", "Classes", "Settings"][index])
        for i, button in enumerate(self.nav_buttons):
            button.setProperty("navActive", "true" if i == index else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if index == 1:
            self._refresh_leaderboard()

    def _refresh_class_lists(self):
        classes = self.repo.list_classes()
        current_id = self.current_class.id if self.current_class else None
        if current_id is not None and all(klass.id != current_id for klass in classes):
            self.current_class = None
            self.students = {}
            self.session = Session()
            self.overlay.hide_overlay()
            self.selection_label.setText("Select a class to get started")
            self._enable_action_buttons(False)
            current_id = None
        for combo in (self.class_selector, self.leaderboard_selector):
            previous = combo.blockSignals(True)
            combo.clear()
            combo.addItem("Select a class…", None)
            for klass in classes:
                combo.addItem(klass.name, klass.id)
            if current_id is not None:
                idx = combo.findData(current_id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(previous)
        self._refresh_class_list()
        self._update_header()
        if self.current_class:
            self._load_class(self.current_class.id)
        else:
            self._update_stats()

    def _header_class_changed(self, index):
        if index < 0:
            return
        class_id = self.class_selector.itemData(index)
        if class_id is None:
            if self.current_class:
                self._load_class(None)
            return
        if self.current_class is None or self.current_class.id != class_id:
            self._load_class(class_id)

    def _load_class(self, class_id):
        self.overlay.hide_overlay()
        if class_id is None:
            self.current_class = None
            self.students = {}
            self.session = Session()
            self.selection_label.setText("Select a class to get started")
            self._enable_action_buttons(False)
        else:
            klass = self.repo.get_class(class_id)
            if klass is None:
                return
            self.current_class = klass
            combo_index = self.leaderboard_selector.findData(class_id)
            if combo_index >= 0 and self.leaderboard_selector.currentIndex() != combo_index:
                self.leaderboard_selector.blockSignals(True)
                self.leaderboard_selector.setCurrentIndex(combo_index)
                self.leaderboard_selector.blockSignals(False)
            students = self.repo.list_students(class_id)
            self.students = {student.name: student for student in students}
            names = list(self.students)
            # Reload this class's persisted session (attendance, skips,
            # last-picked, per-session counters) instead of resetting it.
            self.session.class_id = class_id
            self.session.load_payload(self.repo.get_class_session(class_id), names)
            self.selection_label.setText("Ready to pick!")
            self._enable_action_buttons(bool(students))
        self._render_attendance()
        self._update_stats()
        self._update_header()
        self._refresh_leaderboard()

    def _render_attendance(self):
        while self.attendance_grid.count():
            item = self.attendance_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.current_class:
            return
        self._building_attendance = True
        for index, name in enumerate(sorted(self.students, key=str.casefold)):
            chip = QCheckBox(name)
            chip.setChecked(name in self.session.present)
            chip.setStyleSheet("QCheckBox { background:#D1FAE5; border:1px solid #6EE7B7; border-radius:7px; padding:8px; } QCheckBox:unchecked { background:#F1F5F9; border-color:#E2E8F0; }")
            chip.toggled.connect(lambda present, n=name: self._attendance_changed(n, present))
            self.attendance_grid.addWidget(chip, index // 4, index % 4)
        self._building_attendance = False

    def _attendance_changed(self, name, present):
        if self._building_attendance:
            return
        self.session.toggle_attendance(name, present)
        self._persist_session()
        self._update_stats()

    def select_all(self):
        self.session.select_all(self.students)
        self._persist_session()
        self._render_attendance()
        self._update_stats()

    def deselect_all(self):
        self.session.deselect_all()
        self._persist_session()
        self._render_attendance()
        self._update_stats()

    def start_new_session(self):
        if not self.current_class:
            return self.toast("Select a class first.", "warning")
        self.session.reset_for_new_session(self.students)
        self._persist_session()
        self.overlay.hide_overlay()
        self.selection_label.setText("Ready to pick!")
        self.correct_button.setEnabled(False)
        self.incorrect_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self._render_attendance()
        self._update_stats()
        self.toast("New session started — everyone present.", "success")

    def reset_session_skips(self):
        if not self.current_class:
            return self.toast("Select a class first.", "warning")
        self.session.reset_skips()
        self._persist_session()
        self.toast("Session skips reset.", "success")

    def _persist_session(self):
        if self.current_class:
            self.repo.save_class_session(self.current_class.id, self.session.to_payload())

    def _enable_action_buttons(self, enabled):
        for button in (self.pick_button, self.teacher_button, self.volunteer_button):
            button.setEnabled(enabled)
        for button in (self.correct_button, self.incorrect_button, self.skip_button):
            button.setEnabled(False)

    def _update_stats(self):
        students = list(self.students.values())
        values = {
            "students": len(students), "present": len(self.session.present),
            "picks": sum(s.picks for s in students), "correct": sum(s.correct for s in students),
            "volunteers": sum(s.volunteers for s in students), "skips": sum(s.skips for s in students),
        }
        for key, value in values.items():
            self.stat_cards[key].set_value(value)
        self._update_header()

    def _update_header(self):
        total = len(self.students)
        if self.current_class:
            self.attendance_chip.setText(f"{len(self.session.present)} / {total} present")
        else:
            self.attendance_chip.setText("No class selected")
        if self.settings.overlay_enabled:
            self.overlay_chip.setText(self.overlay.monitor_status or "Overlay on")
            self.overlay_chip.setStyleSheet("background:#EEF2FF;color:#4338CA;border-radius:14px;padding:7px 12px;font-weight:600;")
        else:
            self.overlay_chip.setText("Overlay off")
            self.overlay_chip.setStyleSheet("background:#F1F5F9;color:#64748B;border-radius:14px;padding:7px 12px;font-weight:600;")

    def _refresh_students(self):
        if self.current_class:
            self.students = {s.name: s for s in self.repo.list_students(self.current_class.id)}

    def pick_random(self):
        if not self.current_class:
            return self.toast("Select a class first.", "warning")
        try:
            name = pick_random(self.session.present, self.students, self.settings, self.session.last_picked)
        except ValueError:
            return self.toast("No students present!", "danger")
        self._select_student(name, volunteer=False)

    def teacher_pick(self):
        if not self.current_class:
            return self.toast("Select a class first.", "warning")
        dialog = StudentPickDialog(
            sorted(self.students, key=str.casefold),
            self.session.present,
            "🍎 Teacher Pick",
            True,
            self,
            session_stats=self.session.session_stats,
            last_picked=self.session.last_picked,
            mode="teacher",
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_name:
            self._select_student(dialog.selected_name, volunteer=False)

    def volunteer_pick(self):
        if not self.current_class:
            return self.toast("Select a class first.", "warning")
        names = sorted(self.session.present, key=str.casefold)
        if not names:
            return self.toast("No students present!", "danger")
        dialog = StudentPickDialog(
            names,
            self.session.present,
            "🙋 Who volunteered?",
            False,
            self,
            session_stats=self.session.session_stats,
            last_picked=self.session.last_picked,
            mode="volunteer",
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_name:
            self._select_student(dialog.selected_name, volunteer=True)

    def _select_student(self, name, volunteer):
        self.overlay.hide_overlay()
        self.session.current_student = name
        self.session.last_picked = name
        self.volunteer_current = volunteer
        self.repo.apply_event(self.current_class.id, name, "picks")
        self.session.record_event(name, "picks")
        if volunteer:
            self.repo.apply_event(self.current_class.id, name, "volunteers")
            self.session.record_event(name, "volunteers")
        self._persist_session()
        self._refresh_students()
        self.selection_label.setText(("🙋  " if volunteer else "") + name)
        self.selection_label.setStyleSheet("font-size:32px;font-weight:750;color:#4F46E5;background:#EEF2FF;border-radius:10px;")
        self.correct_button.setEnabled(True)
        self.incorrect_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        if self.settings.overlay_enabled:
            self.overlay.monitor_status = self.overlay.show_student(name, volunteer)
        self._update_stats()

    def mark_result(self, result):
        name = self.session.current_student
        if not name or not self.current_class:
            return
        self.repo.apply_event(self.current_class.id, name, result)
        self.session.record_event(name, result)
        self._persist_session()
        self._clear_current()

    def mark_skip(self):
        name = self.session.current_student
        if not name or not self.current_class:
            return
        if not self.session.can_skip(name, self.settings.skip_limit):
            return self.toast(f"{name} has used all skips for this session.", "danger")
        self.repo.apply_event(self.current_class.id, name, "skips")
        self.session.record_skip(name)
        self.session.record_event(name, "skips")
        self._persist_session()
        self._clear_current()

    def clear_selection(self):
        if self.session.current_student:
            self._clear_current()

    def _clear_current(self):
        self.session.clear_current()
        self.overlay.hide_overlay()
        self.selection_label.setText("Ready to pick!" if self.current_class else "Select a class to get started")
        self.correct_button.setEnabled(False)
        self.incorrect_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self._refresh_students()
        self._update_stats()
        self._refresh_leaderboard()

    # --------------------------------------------------------------- classes
    def create_class(self):
        try:
            names = self.new_class_students.toPlainText().splitlines()
            klass = self.repo.create_class(self.new_class_name.text(), names)
        except ValueError as exc:
            return self.toast(str(exc), "danger")
        self.new_class_name.clear()
        self.new_class_students.clear()
        self._refresh_class_lists()
        self.class_selector.setCurrentIndex(self.class_selector.findData(klass.id))
        self.toast(f"Created {klass.name} ({klass.student_count} students).", "success")

    def _refresh_class_list(self):
        if not hasattr(self, "classes_list"):
            return
        while self.classes_list.count():
            item = self.classes_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for klass in self.repo.list_classes():
            row = QFrame()
            row.setObjectName("Card")
            hl = QHBoxLayout(row)
            title = QLabel(f"<b>{klass.name}</b><br><span style='color:#64748B'>{klass.student_count} students</span>")
            hl.addWidget(title, 1)
            open_btn = self._button("Open", "", lambda _=False, cid=klass.id: self.class_selector.setCurrentIndex(self.class_selector.findData(cid)))
            edit_btn = self._button("Edit", "", lambda _=False, k=klass: self.edit_class(k))
            delete_btn = self._button("Delete", "danger", lambda _=False, cid=klass.id, name=klass.name: self.delete_class(cid, name))
            hl.addWidget(open_btn)
            hl.addWidget(edit_btn)
            hl.addWidget(delete_btn)
            self.classes_list.addWidget(row)

    def edit_class(self, klass):
        is_current = bool(self.current_class and self.current_class.id == klass.id)
        dialog = ClassEditDialog(self.repo, klass, self, session=self.session if is_current else None)
        dialog.exec()
        if is_current:
            self._persist_session()
        self._refresh_class_lists()
        self._render_attendance()
        self._update_stats()
        self.toast("Class updated.", "success")

    def delete_class(self, class_id, name):
        if QMessageBox.question(self, "Delete class", f'Delete "{name}" and all its stats?') != QMessageBox.StandardButton.Yes:
            return
        self.repo.delete_class(class_id)
        if self.current_class and self.current_class.id == class_id:
            self._load_class(None)
        self._refresh_class_lists()
        self.toast("Class deleted.", "success")

    # --------------------------------------------------------------- import
    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import tracker data", "", "Tracker files (*.json *.csv *.txt);;JSON backups (*.json *.txt);;Class CSV (*.csv)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
            if Path(path).suffix.casefold() == ".csv":
                self._import_csv(path, text)
            else:
                data = parse_backup_json(text)
                dialog = ImportModeDialog(self)
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                if dialog.mode == "replace":
                    answer = QMessageBox.warning(self, "Replace all data", "This permanently deletes all existing classes. Continue?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
                    if answer != QMessageBox.StandardButton.Yes:
                        return
                    counts = self.repo.replace_all(data)
                else:
                    counts = self.repo.merge_all(data)
                imported_settings = extract_backup_settings(text)
                if imported_settings:
                    self._apply_imported_settings(imported_settings)
                self._refresh_class_lists()
                self.toast(f"Imported {counts[0]} classes, {counts[1]} students.", "success")
        except (OSError, ImportError, ValueError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def _import_csv(self, path, text):
        rows = parse_class_csv(text)
        if not rows:
            return self.toast("CSV contains no student rows.", "warning")
        default = Path(path).stem
        if default.endswith("_statistics"):
            default = default[:-11]
        default = default.replace("_", " ").strip()
        class_name, ok = QInputDialogText.get(self, "CSV class", "Destination class name:", default)
        if not ok or not class_name.strip():
            return
        klass = self.repo.get_class_by_name(class_name.strip())
        if klass:
            dialog = ImportModeDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            if dialog.mode == "replace":
                self.repo.delete_class(klass.id)
                klass = None
        if not klass:
            # CSV is a per-class student stats import; may contain no student rows.
            if not rows:
                return self.toast("CSV contains no student rows.", "warning")
            klass = self.repo.create_class(class_name, [name for name, _ in rows])
        for name, stats in rows:
            self.repo.set_stats(klass.id, name, stats)
        self._refresh_class_lists()
        self.toast(f"Imported 1 class, {len(rows)} students.", "success")

    # --------------------------------------------------------------- exports
    def export_backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export backup", "ParticipationTracker_Backup.json", "JSON backup (*.json)")
        if not path:
            return
        classes = {}
        for klass in self.repo.list_classes():
            classes[klass.name] = {"students": {s.name: s.counters() for s in self.repo.list_students(klass.id)}}
        try:
            export_backup(path, classes, self.settings)
            self.toast("Backup exported.", "success")
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def export_current_csv(self):
        class_id = self.leaderboard_selector.currentData()
        if class_id is None and self.current_class:
            class_id = self.current_class.id
        klass = self.repo.get_class(class_id) if class_id else None
        if not klass:
            return self.toast("Select a class first.", "warning")
        default_name = f"{klass.name}_statistics.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export class CSV", default_name, "CSV (*.csv)")
        if not path:
            return
        try:
            export_csv(path, klass.name, self.repo.list_students(klass.id), self.settings)
            self.toast("CSV exported.", "success")
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    # ----------------------------------------------------------- leaderboard
    def _refresh_leaderboard(self, *_):
        if not hasattr(self, "leaderboard_table"):
            return
        class_id = self.leaderboard_selector.currentData()
        if class_id is None:
            class_id = self.current_class.id if self.current_class else None
        students = self.repo.list_students(class_id) if class_id else []
        students.sort(key=lambda s: leaderboard_score(s, self.settings), reverse=True)
        self.leaderboard_table.setSortingEnabled(False)
        self.leaderboard_table.setRowCount(len(students))
        for idx, student in enumerate(students, 1):
            points = participation_points(student, self.settings)
            score = leaderboard_score(student, self.settings)
            values = [idx, student.name, student.picks, student.volunteers, student.skips, student.correct, student.incorrect, f"{points:.2f}", f"{score:.2f}" if student.picks else "—"]
            for col, value in enumerate(values):
                sort_value = None
                if col in (0, 2, 3, 4, 5, 6, 7):
                    sort_value = float(value)
                elif col == 8:
                    sort_value = score if student.picks else float("-inf")
                item = _SortableItem(str(value), sort_value)
                if col != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 5:
                    item.setForeground(Qt.GlobalColor.darkGreen)
                elif col == 6:
                    item.setForeground(Qt.GlobalColor.red)
                if col in (7, 8):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.leaderboard_table.setItem(idx - 1, col, item)
        self.leaderboard_table.setSortingEnabled(True)

    def reset_stats(self):
        class_id = self.leaderboard_selector.currentData()
        if class_id is None and self.current_class:
            class_id = self.current_class.id
        klass = self.repo.get_class(class_id) if class_id else None
        if not klass:
            return self.toast("Select a class first.", "warning")
        if QMessageBox.question(self, "Reset stats", f'Reset all stats for "{klass.name}"?') != QMessageBox.StandardButton.Yes:
            return
        is_current = bool(self.current_class and self.current_class.id == klass.id)
        if is_current and self.session.current_student:
            self._clear_current()
        self.repo.reset_class_stats(klass.id)
        self._refresh_students()
        if is_current:
            self.session.reset_skips()
            self.session.session_stats = {
                name: {field: 0 for field in COUNTER_FIELDS} for name in self.students
            }
            self._persist_session()
        self._refresh_leaderboard()
        self._update_stats()
        self.toast("Leaderboard reset.", "success")

    # --------------------------------------------------------------- settings
    def save_settings(self):
        self.settings.skip_limit = self.skip_limit.value()
        self.settings.weighted_enabled = self.weighted_enabled.isChecked()
        for key, (direction, amount) in self.weight_controls.items():
            setattr(self.settings, f"weight_{key}_dir", direction.currentText())
            setattr(self.settings, f"weight_{key}_amt", amount.value())
        for key, (effect, points) in self.scoring_controls.items():
            setattr(self.settings, f"scoring_{key}_effect", effect.currentText())
            setattr(self.settings, f"scoring_{key}_points", points.value())
        self.repo.save_settings(self.settings)
        self._refresh_leaderboard()
        self._update_formula()
        self.toast("Settings saved.", "success")

    def _apply_settings_to_form(self):
        """Push the in-memory settings into the Settings page widgets."""
        self.skip_limit.setValue(self.settings.skip_limit)
        self.weighted_enabled.setChecked(self.settings.weighted_enabled)
        for key, (direction, amount) in self.weight_controls.items():
            direction.setCurrentText(getattr(self.settings, f"weight_{key}_dir"))
            amount.setValue(getattr(self.settings, f"weight_{key}_amt"))
        for key, (effect, points) in self.scoring_controls.items():
            effect.setCurrentText(getattr(self.settings, f"scoring_{key}_effect"))
            points.setValue(getattr(self.settings, f"scoring_{key}_points"))
        self.overlay_toggle.blockSignals(True)
        self.overlay_toggle.setChecked(self.settings.overlay_enabled)
        self.overlay_toggle.blockSignals(False)
        self._update_formula()

    def _apply_imported_settings(self, values: dict):
        valid = set(Settings.__dataclass_fields__)
        for key, value in values.items():
            if key in valid:
                setattr(self.settings, key, value)
        self.repo.save_settings(self.settings)
        self._apply_settings_to_form()
        if not self.settings.overlay_enabled:
            self.overlay.hide_overlay()
        elif self.session.current_student:
            self.overlay.monitor_status = self.overlay.show_student(
                self.session.current_student, self.volunteer_current
            )
        self._update_header()
        self._refresh_leaderboard()

    def _toggle_overlay(self, enabled):
        self.settings.overlay_enabled = enabled
        self.repo.save_settings(self.settings)
        if not enabled:
            self.overlay.hide_overlay()
        elif self.session.current_student:
            self.overlay.monitor_status = self.overlay.show_student(self.session.current_student, self.volunteer_current)
        self._update_header()

    def _update_formula(self, *_):
        if not hasattr(self, "scoring_controls"):
            return
        terms = []
        for key, (label, count) in {
            "correct": ("correct", "correct"), "volunteer": ("volunteers", "volunteers"),
            "incorrect": ("incorrect", "incorrect"), "skip": ("skips", "skips"),
        }.items():
            effect, points = self.scoring_controls[key]
            sign = "+" if effect.currentText() == "add" else "−"
            terms.append(f"{sign} ({label} × {points.value():g})")
        self.formula_preview.setText("Total Points = " + " ".join(terms) + "\nLeaderboard Score = Total Points ÷ Times Picked")

    # ---------------------------------------------------------------- toast
    def toast(self, message, kind="info"):
        color = {"success": COLORS["success"], "danger": COLORS["danger"], "warning": COLORS["warning"], "info": COLORS["info"]}.get(kind, COLORS["info"])
        self.statusBar().setStyleSheet(f"QStatusBar {{ background: {color}; color: white; padding: 4px; }}")
        self.statusBar().showMessage(message, 3500)
        QTimer.singleShot(3600, lambda: self.statusBar().setStyleSheet(""))

    def closeEvent(self, event):
        self.overlay.hide_overlay()
        event.accept()


class QInputDialogText:
    """Small custom text prompt wrapper; avoids keeping another page dependency."""
    @staticmethod
    def get(parent, title, label, default=""):
        from PySide6.QtWidgets import QInputDialog
        return QInputDialog.getText(parent, title, label, text=default)
