"""Main application window and four functional tracker pages."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QDoubleSpinBox, QStackedWidget,
    QStatusBar, QTableWidget, QTableWidgetItem, QTableView, QTextEdit, QVBoxLayout, QWidget,
)

from ..db.repository import Repository
from ..models import COUNTER_FIELDS, Class, Settings, Student
from ..overlay import OverlayWindow
from .. import sound
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
        if isinstance(other, QTableWidgetItem):
            if isinstance(other, _SortableItem) and self.sort_value is not None and other.sort_value is not None:
                return self.sort_value < other.sort_value
            # Do not delegate to QTableWidgetItem.__lt__ here: PySide can route
            # that call back through this Python override while sorting text cells.
            return self.text().casefold() < other.text().casefold()
        return False


class MainWindow(QMainWindow):
    def __init__(self, repository: Repository, fallback_data_dir: bool = False):
        super().__init__()
        self.repo = repository
        self.settings = repository.get_settings()
        self.session = Session()
        self.current_class: Class | None = None
        self.students: dict[str, Student] = {}
        self.volunteer_current = False
        self._pick_kind = "random"
        self.overlay = OverlayWindow(self)
        self._building_attendance = False
        self.setWindowTitle("Participation Tracker")
        self._compact = False
        self._stat_columns = 6
        self._attendance_columns = 4
        self._settings_stacked = False
        self._attendance_chips = []
        self._nav_icons = []
        self._nav_labels = []
        self.resize(1250, 850)
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
        self.sidebar = sidebar
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        self.sidebar_layout = side
        side.setContentsMargins(16, 24, 16, 18)
        brand = QLabel("🎯  Participation\n      Tracker")
        self.brand = brand
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
            self._nav_icons.append(icon)
            self._nav_labels.append(label)
        side.addStretch(1)
        self.overlay_toggle = QCheckBox("Second monitor overlay")
        self.overlay_toggle.setToolTip("Second monitor overlay")
        self.overlay_toggle.setStyleSheet("color: #CBD5E1; padding: 8px 2px;")
        self.overlay_toggle.setChecked(self.settings.overlay_enabled)
        self.overlay_toggle.toggled.connect(self._toggle_overlay)
        side.addWidget(self.overlay_toggle)
        outer.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.content_layout = content_layout
        content_layout.setContentsMargins(28, 20, 28, 20)
        content_layout.setSpacing(16)
        header = QHBoxLayout()
        self.page_title = QLabel("Picker")
        self.page_title.setObjectName("PageTitle")
        header.addWidget(self.page_title)
        header.addStretch(1)
        self.class_label = QLabel("Class")
        header.addWidget(self.class_label)
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
        self._update_responsive_layout()

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
        self._stat_keys = []
        self.stat_grid = QGridLayout()
        self.stat_grid.setSpacing(10)
        for i, (key, title) in enumerate((("students", "Total Students"), ("present", "Present"), ("picks", "Total Picks"), ("correct", "Correct"), ("volunteers", "Volunteers"), ("skips", "Skips"))):
            card = StatCard(title)
            self.stat_grid.addWidget(card, 0, i)
            self.stat_cards[key] = card
            self._stat_keys.append(key)
        layout.addLayout(self.stat_grid)

        frame, card_layout = self._card(layout)
        card_layout.addWidget(self._section_title("Current selection"))
        self.selection_label = QLabel("Select a class to get started")
        self.selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_label.setMinimumHeight(105)
        self._apply_selection_style()
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
        self.attendance_title = self._section_title("Attendance")
        self._attendance_buttons = [
            self._button("🔄 Start new session", "info", self.start_new_session),
            self._button("Reset session skips", "", self.reset_session_skips),
            self._button("Select all", "", self.select_all),
            self._button("Deselect all", "", self.deselect_all),
        ]
        self.attendance_title_row = QHBoxLayout()
        self.attendance_title_row.addWidget(self.attendance_title)
        self.attendance_title_row.addStretch(1)
        attendance.addLayout(self.attendance_title_row)
        self.attendance_actions = QWidget()
        self.attendance_actions_grid = QGridLayout(self.attendance_actions)
        self.attendance_actions_grid.setContentsMargins(0, 0, 0, 0)
        self.attendance_actions_grid.setSpacing(6)
        self.attendance_actions.setVisible(False)
        attendance.addWidget(self.attendance_actions)
        self._set_button_flow(self.attendance_title_row, self.attendance_actions_grid, self.attendance_actions,
                              self._attendance_buttons, self._compact, leading=(self.attendance_title,))
        self.attendance_scroll = QScrollArea()
        self.attendance_scroll.setWidgetResizable(True)
        self.attendance_scroll.setMaximumHeight(220)
        self.attendance_widget = QWidget()
        self.attendance_widget.setObjectName("Panel")
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
        # The class is selected once, in the shared header selector above; this page
        # deliberately has no class selector of its own so the class name (and the
        # choice) is not duplicated.
        self.leaderboard_toolbar = QHBoxLayout()
        self.leaderboard_summary_toggle = QCheckBox("Show summary on extended display")
        self.leaderboard_summary_toggle.setEnabled(False)
        self.leaderboard_summary_toggle.toggled.connect(self._toggle_leaderboard_summary)
        self._leaderboard_buttons = [
            self._button("📊 Export CSV", "success", self.export_current_csv),
            self._button("🗑 Reset stats", "danger", self.reset_stats),
        ]
        self.leaderboard_actions = QWidget()
        self.leaderboard_actions_grid = QGridLayout(self.leaderboard_actions)
        self.leaderboard_actions_grid.setContentsMargins(0, 0, 0, 0)
        self.leaderboard_actions_grid.setSpacing(6)
        self.leaderboard_actions.setVisible(False)
        layout.addLayout(self.leaderboard_toolbar)
        layout.addWidget(self.leaderboard_actions)
        self._set_button_flow(self.leaderboard_toolbar, self.leaderboard_actions_grid,
                              self.leaderboard_actions, self._leaderboard_buttons,
                              self._compact, leading=(self.leaderboard_summary_toggle,), stretch_at=0)
        self.leaderboard_table = QTableWidget(0, 9)
        self.leaderboard_table.setHorizontalHeaderLabels(["Rank", "Name", "Picks", "Volunteers", "Skips", "Correct", "Incorrect", "Total Points", "Score"])
        for column, tip in (
            (7, "Total participation points"),
            (8, "Leaderboard score = (Correct × correct value ÷ Times Picked)"
             " + (Volunteers × volunteer value) + (Skips × skip value)"
             " + (Incorrect × incorrect value). Values and Add/Subtract effects come from Settings."),
        ):
            self.leaderboard_table.horizontalHeaderItem(column).setToolTip(tip)
        self.leaderboard_table.setAlternatingRowColors(True)
        self.leaderboard_table.setSortingEnabled(True)
        self.leaderboard_table.setWordWrap(False)
        self.leaderboard_table.verticalHeader().setVisible(False)
        header = self.leaderboard_table.horizontalHeader()
        # Tighter header padding keeps the numeric columns compact.
        header.setStyleSheet("QHeaderView::section { padding: 4px 6px; }")
        for column in range(self.leaderboard_table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)   # the last column fills the spare width
        self.leaderboard_table.setStyleSheet("QTableWidget { background: white; border: none; border-radius: 0; }")
        self.leaderboard_table.setColumnHidden(0, True)
        self.leaderboard_table.setColumnHidden(1, True)
        # Rank and Name live in a frozen view pinned to the left edge, so they stay
        # visible while the statistics columns scroll horizontally beneath it.
        self.leaderboard_frozen = QTableView()
        frozen = self.leaderboard_frozen
        frozen.setModel(self.leaderboard_table.model())
        frozen.setSelectionModel(self.leaderboard_table.selectionModel())
        for column in range(2, self.leaderboard_table.columnCount()):
            frozen.setColumnHidden(column, True)
        frozen.setAlternatingRowColors(True)
        frozen.setSortingEnabled(True)
        frozen.setWordWrap(False)
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.verticalHeader().setVisible(False)
        frozen.verticalHeader().setDefaultSectionSize(self.leaderboard_table.verticalHeader().defaultSectionSize())
        frozen.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        frozen.horizontalHeader().setStretchLastSection(True)   # Name fills spare width
        frozen.horizontalHeader().setStyleSheet("QHeaderView::section { padding: 4px 6px; border: 0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0; font-weight: 700; background: #F1F5F9; }")
        frozen.setStyleSheet("QTableView { background: white; border: none; border-right: 1px solid #E2E8F0; gridline-color: #E2E8F0; alternate-background-color: #F8FAFC; }")
        frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table_header = self.leaderboard_table.horizontalHeader()
        frozen_header = frozen.horizontalHeader()

        def mirror_sort(source_header, target_header, column, order):
            # Setting an identical indicator emits nothing, so this cannot loop.
            if target_header.sortIndicatorSection() != column or target_header.sortIndicatorOrder() != order:
                target_header.setSortIndicator(column, order)

        table_header.sortIndicatorChanged.connect(lambda c, o: mirror_sort(table_header, frozen_header, c, o))
        frozen_header.sortIndicatorChanged.connect(lambda c, o: mirror_sort(frozen_header, table_header, c, o))
        self.leaderboard_table.verticalScrollBar().valueChanged.connect(frozen.verticalScrollBar().setValue)
        table_frame = QFrame()
        self.leaderboard_frame = table_frame
        table_frame.setStyleSheet("QFrame { background: white; border: 1px solid #E2E8F0; border-radius: 8px; }")
        table_inner = QHBoxLayout(table_frame)
        table_inner.setContentsMargins(0, 0, 0, 0)
        table_inner.setSpacing(0)
        table_inner.addWidget(frozen)
        table_inner.addWidget(self.leaderboard_table, 1)
        layout.addWidget(table_frame, 1)
        self._update_frozen_columns()
        return page

    def _update_frozen_columns(self) -> None:
        """Keep Rank/Name pinned at their readable width at every window width.

        The frozen view is sized to Rank + Name and never shrinks, so names are
        never replaced with an ellipsis; the statistics view scrolls horizontally
        beneath it. When Rank + Name cannot fit alongside the statistics, the
        Rank column yields so the name still reads in full.
        """
        if not hasattr(self, "leaderboard_frozen"):
            return
        frozen = self.leaderboard_frozen
        frozen_header = frozen.horizontalHeader()
        frozen_header.setStretchLastSection(False)
        frozen_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        rank_width = frozen_header.sectionSize(0)
        name_width = frozen_header.sectionSize(1)
        rail = 56 if self._compact else 220
        margins = 24 if self._compact else 56
        # The leaderboard frame's width: the page margins sit inside it.
        frame_width = max(240, self.width() - rail - margins) - 20
        stats_floor = 60   # the statistics columns keep room to scroll
        rank_fits = rank_width + name_width + 2 <= frame_width - stats_floor
        frozen.setColumnHidden(0, not rank_fits)
        contents = name_width if not rank_fits else rank_width + name_width + 2
        frozen.setFixedWidth(max(140, min(contents, frame_width - stats_floor) + 2))

    def _build_classes_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # The page scrolls instead of squeezing the class cards when the window
        # is short, so names, counts, and the row buttons stay readable.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
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
        self.create_actions_row = row
        self._create_buttons = [
            self._button("Create class", "primary", self.create_class),
            self._button("📥 Import JSON / CSV", "info", self.import_file),
            self._button("📤 Export backup", "", self.export_backup),
        ]
        self.create_actions = QWidget()
        self.create_actions_grid = QGridLayout(self.create_actions)
        self.create_actions_grid.setContentsMargins(0, 0, 0, 0)
        self.create_actions_grid.setSpacing(6)
        self.create_actions.setVisible(False)
        form.addLayout(row)
        form.addWidget(self.create_actions)
        self._set_button_flow(row, self.create_actions_grid, self.create_actions, self._create_buttons,
                              self._compact, stretch_at=1)
        list_card, list_layout = self._card(layout)
        list_layout.addWidget(self._section_title("Your classes"))
        self.classes_list = QVBoxLayout()
        self.classes_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        list_layout.addLayout(self.classes_list)
        # Absorb spare height so the title stays at the top of the card.
        list_layout.addStretch(1)
        layout.addWidget(list_card, 1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return page

    def _build_settings_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        layout = QVBoxLayout(form_widget)
        layout.setContentsMargins(6, 6, 6, 6)
        self._settings_rows = []
        frame, form = self._card(layout, (12, 12, 12, 12))
        form.addWidget(self._section_title("Session"))
        panel = self._settings_panel(form)
        self.skip_limit = QSpinBox()
        self.skip_limit.setRange(0, 100)
        self.skip_limit.setValue(self.settings.skip_limit)
        self._settings_row(panel, "Skip limit per student (0 = unlimited)", [self.skip_limit], right_align=True)
        self.chime_enabled = QCheckBox("Play a chime when a student is picked")
        self.chime_enabled.setChecked(self.settings.chime_enabled)
        panel.addWidget(self.chime_enabled)
        frame2, weighted = self._card(layout, (12, 12, 12, 12))
        weighted.addWidget(self._section_title("Weighted random selection"))
        panel = self._settings_panel(weighted)
        self.weighted_enabled = QCheckBox("Enable fair weighted random selection")
        self.weighted_enabled.setChecked(self.settings.weighted_enabled)
        panel.addWidget(self.weighted_enabled)
        self.weight_controls = {}
        for key, label, default_dir, amt in (
            ("volunteer", "Volunteer events", "decrease", 30),
            ("correct", "Correct answers", "decrease", 15),
            ("incorrect", "Incorrect answers", "increase", 10),
            ("skip", "Skips", "increase", 20),
        ):
            direction = QComboBox()
            direction.addItems(["decrease", "increase"])
            direction.setCurrentText(getattr(self.settings, f"weight_{key}_dir"))
            direction.currentTextChanged.connect(self._refresh_choice_colors)
            amount = QSpinBox()
            amount.setRange(0, 1000)
            amount.setValue(getattr(self.settings, f"weight_{key}_amt"))
            self._settings_row(panel, label, [direction, QLabel("weight per event"), amount])
            self.weight_controls[key] = (direction, amount)
        frame3, scoring = self._card(layout, (12, 12, 12, 12))
        scoring.addWidget(self._section_title("Participation scoring"))
        panel = self._settings_panel(scoring)
        self.scoring_controls = {}
        for key, label in (("correct", "Correct response"), ("volunteer", "Volunteer"), ("incorrect", "Incorrect response"), ("skip", "Skip")):
            effect = QComboBox()
            effect.addItems(["add", "subtract"])
            effect.setCurrentText(getattr(self.settings, f"scoring_{key}_effect"))
            effect.currentTextChanged.connect(self._refresh_choice_colors)
            points = QDoubleSpinBox()
            points.setRange(0, 1000)
            points.setSingleStep(0.5)
            points.setValue(getattr(self.settings, f"scoring_{key}_points"))
            self._settings_row(panel, label, [effect, QLabel("points"), points])
            self.scoring_controls[key] = (effect, points)
        self.formula_preview = QLabel()
        self.formula_preview.setWordWrap(True)
        self.formula_preview.setStyleSheet("background:#EEF2FF;color:#3730A3;border-radius:8px;padding:10px;")
        scoring.addWidget(self.formula_preview)
        layout.addStretch(1)
        scroll.setWidget(form_widget)
        self._settings_scroll = scroll
        self._settings_inner = form_widget
        outer.addWidget(scroll, 1)
        # Keep the save action visible without scrolling.
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self._button("Save settings", "primary", self.save_settings))
        outer.addLayout(save_row)
        self._update_formula()
        for pair in self.scoring_controls.values():
            pair[1].valueChanged.connect(self._update_formula)
        self._layout_settings_rows()
        self._refresh_choice_colors()
        return page

    def _settings_panel(self, card_layout) -> QVBoxLayout:
        """Light panel behind a card's values, matching the picker's attendance area."""
        panel = QWidget()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 8, 10, 8)
        panel_layout.setSpacing(8)
        card_layout.addWidget(panel)
        return panel_layout

    def _settings_row(self, panel_layout, label_text: str, controls: list, *, right_align: bool = False):
        """Remember a settings row so it can switch between one and two lines."""
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        panel_layout.addWidget(row)
        self._settings_rows.append((grid, QLabel(label_text), controls, right_align))

    def _layout_settings_rows(self):
        """One line per setting, or the label above its controls when space is tight."""
        for grid, label, controls, right_align in self._settings_rows:
            while grid.count():
                grid.takeAt(0)
            for column in range(8):
                grid.setColumnStretch(column, 0)
            if self._settings_stacked:
                grid.addWidget(label, 0, 0, 1, max(1, len(controls)))
                for index, widget in enumerate(controls):
                    grid.addWidget(widget, 1, index)
                grid.setColumnStretch(len(controls), 1)
            else:
                grid.addWidget(label, 0, 0)
                column = 1
                if right_align:
                    grid.setColumnStretch(column, 1)
                    column += 1
                for widget in controls:
                    grid.addWidget(widget, 0, column)
                    column += 1
                grid.setColumnStretch(column, 1)
        # Re-adding the same widgets keeps layout caches stale; shrinking the form
        # forces the scroll area to re-measure it immediately.
        inner = getattr(self, "_settings_inner", None)
        if inner is not None:
            inner.resize(1, 1)

    def _refresh_choice_colors(self, *_):
        """Tint add/subtract and increase/decrease so the choice reads at a glance."""
        for direction, _amount in self.weight_controls.values():
            flag = "positive" if direction.currentText() == "increase" else "caution"
            self._set_choice_flag(direction, flag)
        for effect, _points in self.scoring_controls.values():
            flag = "positive" if effect.currentText() == "add" else "negative"
            self._set_choice_flag(effect, flag)

    @staticmethod
    def _set_choice_flag(combo, flag: str) -> None:
        if combo.property("flag") == flag:
            return
        combo.setProperty("flag", flag)
        combo.style().unpolish(combo)
        combo.style().polish(combo)

    def _button(self, text, variant, callback):
        button = QPushButton(text)
        if variant:
            button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    # ------------------------------------------------------------ responsive
    def _update_responsive_layout(self):
        """Adapt the window down to a quarter of the main monitor's width."""
        if not hasattr(self, "stat_grid"):
            return
        screen = QGuiApplication.primaryScreen()
        monitor_width = screen.geometry().width() if screen else 1920
        self.setMinimumSize(max(360, round(monitor_width * 0.25)), 650)

        compact = self.width() < 940
        if compact != self._compact:
            self._compact = compact
            self.sidebar.setFixedWidth(56 if compact else 220)
            if compact:
                self.sidebar_layout.setContentsMargins(8, 16, 8, 12)
            else:
                self.sidebar_layout.setContentsMargins(16, 24, 16, 18)
            self.brand.setText("🎯" if compact else "🎯  Participation\n      Tracker")
            self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter if compact else Qt.AlignmentFlag.AlignLeft)
            for index, button in enumerate(self.nav_buttons):
                button.setText(self._nav_icons[index] if compact else f"{self._nav_icons[index]}    {self._nav_labels[index]}")
                button.setToolTip(self._nav_labels[index] if compact else "")
                button.setProperty("navCompact", "true" if compact else "false")
                button.style().unpolish(button)
                button.style().polish(button)
            self.overlay_toggle.setText("🖥" if compact else "Second monitor overlay")
            self.content_layout.setContentsMargins(*(12, 12, 12, 12) if compact else (28, 20, 28, 20))
            # In a narrow window the header keeps the page title (smaller) and the
            # class selector; the counts live on the Picker page and the overlay
            # state on the sidebar switch.
            self.page_title.setStyleSheet("font-size: 18px; font-weight: 700;" if compact else "")
            self.class_label.setVisible(not compact)
            self.attendance_chip.setVisible(not compact)
            self.overlay_chip.setVisible(not compact)
            self.class_selector.setMinimumWidth(130 if compact else 210)
            self._apply_selection_style()
            self._set_button_flow(self.attendance_title_row, self.attendance_actions_grid, self.attendance_actions,
                                  self._attendance_buttons, compact, leading=(self.attendance_title,))
            self._set_button_flow(self.create_actions_row, self.create_actions_grid, self.create_actions,
                                  self._create_buttons, compact, stretch_at=1)
            self._set_button_flow(self.leaderboard_toolbar, self.leaderboard_actions_grid,
                                  self.leaderboard_actions, self._leaderboard_buttons,
                                  compact, leading=(self.leaderboard_summary_toggle,), stretch_at=0)
            self._refresh_class_list()
        rail = 56 if compact else 220
        margins = 24 if compact else 56
        available = max(240, self.width() - rail - margins)
        stat_columns = 6 if available >= 6 * 130 else (3 if available >= 3 * 130 else 2)
        attendance_columns = min(4, max(1, available // 180))
        stacked_settings = available < 420
        if stat_columns != self._stat_columns:
            self._stat_columns = stat_columns
            self._layout_stat_cards()
        if attendance_columns != self._attendance_columns:
            self._attendance_columns = attendance_columns
            self._layout_attendance_chips()
        if stacked_settings != self._settings_stacked:
            self._settings_stacked = stacked_settings
            self._layout_settings_rows()
        self._update_frozen_columns()

    def _layout_stat_cards(self):
        grid = self.stat_grid
        while grid.count():
            grid.takeAt(0)
        columns = self._stat_columns
        for index, key in enumerate(self._stat_keys):
            grid.addWidget(self.stat_cards[key], index // columns, index % columns)

    def _layout_attendance_chips(self):
        grid = self.attendance_grid
        while grid.count():
            grid.takeAt(0)
        columns = self._attendance_columns
        for index, chip in enumerate(self._attendance_chips):
            grid.addWidget(chip, index // columns, index % columns)

    def _set_button_flow(self, row, grid, container, buttons, compact, leading=(), stretch_at=0):
        """Buttons in one row on wide windows; a 2-column grid on narrow ones.

        ``stretch_at`` is the index of the first button that sits right of the
        stretch, so a leading primary action stays left and the rest go right.
        """
        while row.count():
            row.takeAt(0)
        while grid.count():
            grid.takeAt(0)
        for widget in leading:
            row.addWidget(widget)
        if compact:
            if leading:
                row.addStretch(1)
            for index, button in enumerate(buttons):
                grid.addWidget(button, index // 2, index % 2)
            container.setVisible(True)
            return
        for index, button in enumerate(buttons):
            if index == stretch_at:
                row.addStretch(1)
            row.addWidget(button)
        container.setVisible(False)

    def _apply_selection_style(self):
        size = 22 if self._compact else 32
        self.selection_label.setStyleSheet(f"font-size:{size}px;font-weight:750;color:#4F46E5;background:#EEF2FF;border-radius:10px;")

    def resizeEvent(self, event):
        self._update_responsive_layout()
        super().resizeEvent(event)

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
        combo = self.class_selector
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
            self._refresh_leaderboard()

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
        for chip in self._attendance_chips:
            chip.hide()
            chip.deleteLater()
        self._attendance_chips = []
        if self.current_class:
            self._building_attendance = True
            for name in sorted(self.students, key=str.casefold):
                chip = QCheckBox(name)
                chip.setChecked(name in self.session.present)
                chip.setStyleSheet("QCheckBox { background:#D1FAE5; border:1px solid #6EE7B7; border-radius:7px; padding:8px; } QCheckBox:unchecked { background:#F1F5F9; border-color:#E2E8F0; }")
                chip.toggled.connect(lambda present, n=name: self._attendance_changed(n, present))
                self._attendance_chips.append(chip)
            self._building_attendance = False
        self._layout_attendance_chips()

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
            self._select_student(dialog.selected_name, volunteer=False, mode="teacher")

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
            self._select_student(dialog.selected_name, volunteer=True, mode="volunteer")

    def _select_student(self, name, volunteer, mode="random"):
        """Put a student in the spotlight without counting the pick yet.

        The pick is only recorded once Correct, Incorrect, or Skip is marked, so
        clearing the selection (Esc) never inflates the pick count. A volunteer
        selection is still a volunteer event and is recorded immediately.
        """
        self.overlay.hide_overlay()
        if hasattr(self, "leaderboard_summary_toggle") and self.leaderboard_summary_toggle.isChecked():
            self.dismiss_leaderboard_summary()
        self.session.current_student = name
        self.session.last_picked = name
        self.volunteer_current = volunteer
        self._pick_kind = mode
        if volunteer:
            self.repo.apply_event(self.current_class.id, name, "volunteers")
            self.session.record_event(name, "volunteers")
        self._persist_session()
        self._refresh_students()
        self.selection_label.setText(("🙋  " if volunteer else "") + name)
        self._apply_selection_style()
        self.correct_button.setEnabled(True)
        self.incorrect_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        if self.settings.overlay_enabled:
            self.overlay.monitor_status = self.overlay.show_student(name, mode)
        if self.settings.chime_enabled:
            sound.play_chime()
        self._update_stats()

    def _commit_selection(self):
        """Count the pick for the pending selection (result or skip was marked)."""
        name = self.session.current_student
        if not name or not self.current_class:
            return
        self.repo.apply_event(self.current_class.id, name, "picks")
        self.session.record_event(name, "picks")

    def mark_result(self, result):
        name = self.session.current_student
        if not name or not self.current_class:
            return
        self._commit_selection()
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
        self._commit_selection()
        self.repo.apply_event(self.current_class.id, name, "skips")
        self.session.record_skip(name)
        self.session.record_event(name, "skips")
        self._persist_session()
        self._clear_current()

    def clear_selection(self):
        self.dismiss_leaderboard_summary()
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
                item.widget().hide()
                item.widget().deleteLater()
        for klass in self.repo.list_classes():
            row = QFrame()
            row.setObjectName("Card")
            title = QLabel(f"<b>{klass.name}</b><br><span style='color:#64748B'>{klass.student_count} students</span>")
            open_btn = self._button("Open", "", lambda _=False, cid=klass.id: self.class_selector.setCurrentIndex(self.class_selector.findData(cid)))
            edit_btn = self._button("Edit", "", lambda _=False, k=klass: self.edit_class(k))
            delete_btn = self._button("Delete", "danger", lambda _=False, cid=klass.id, name=klass.name: self.delete_class(cid, name))
            if self._compact:
                # Narrow window: name on its own line so it is never squeezed out.
                vl = QVBoxLayout(row)
                vl.addWidget(title)
                buttons = QHBoxLayout()
                buttons.addWidget(open_btn)
                buttons.addWidget(edit_btn)
                buttons.addWidget(delete_btn)
                buttons.addStretch(1)
                vl.addLayout(buttons)
                vl.addStretch(1)
            else:
                hl = QHBoxLayout(row)
                hl.addWidget(title, 1)
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
        klass = self.current_class
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
        students = self.repo.list_students(self.current_class.id) if self.current_class else []
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
                else:
                    item.setToolTip(student.name)
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
        # Rank 1 is the highest rank, so show it at the top by default.
        self.leaderboard_table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._update_frozen_columns()
        if hasattr(self, "leaderboard_summary_toggle"):
            self.leaderboard_summary_toggle.setEnabled(self.current_class is not None)
            if self.current_class is None and self.leaderboard_summary_toggle.isChecked():
                self.leaderboard_summary_toggle.setChecked(False)
            elif self.leaderboard_summary_toggle.isChecked():
                self._show_leaderboard_summary()

    def _leaderboard_summary_rows(self) -> list[tuple[str, str, str, str, str, str]]:
        """Return all students' Rank, Name, Picks, Volunteers, Total Points, and Score rows."""
        if not self.current_class:
            return []

        # Build the overlay from the class data, not the on-screen table. The
        # table is a presentation widget and may still be refreshing when the
        # class changes; using it here could carry over the previous class's
        # row count and truncate the monitor summary.
        students = self.repo.list_students(self.current_class.id)
        students.sort(key=lambda student: leaderboard_score(student, self.settings), reverse=True)
        rows = []
        for rank, student in enumerate(students, 1):
            points = participation_points(student, self.settings)
            score = leaderboard_score(student, self.settings)
            rows.append((
                str(rank),
                student.name,
                str(student.picks),
                str(student.volunteers),
                f"{points:.2f}",
                f"{score:.2f}" if student.picks else "—",
            ))
        return rows

    def _show_leaderboard_summary(self) -> None:
        if not self.current_class or not hasattr(self, "leaderboard_summary_toggle"):
            return
        self.overlay.monitor_status = self.overlay.show_leaderboard_summary(
            self.current_class.name, self._leaderboard_summary_rows()
        )

    def _toggle_leaderboard_summary(self, enabled: bool) -> None:
        if enabled:
            if not self.current_class:
                self.leaderboard_summary_toggle.setChecked(False)
                return
            self._show_leaderboard_summary()
        elif getattr(self.overlay, "display_mode", None) == "leaderboard":
            self.overlay.hide_overlay()

    def dismiss_leaderboard_summary(self) -> None:
        """Dismiss the monitor summary and synchronize the page checkbox."""
        if not hasattr(self, "leaderboard_summary_toggle"):
            return
        was_checked = self.leaderboard_summary_toggle.isChecked()
        if was_checked:
            self.leaderboard_summary_toggle.blockSignals(True)
            self.leaderboard_summary_toggle.setChecked(False)
            self.leaderboard_summary_toggle.blockSignals(False)
        if was_checked or getattr(self.overlay, "display_mode", None) == "leaderboard":
            self.overlay.hide_overlay()

    def reset_stats(self):
        klass = self.current_class
        if not klass:
            return self.toast("Select a class first.", "warning")
        if QMessageBox.question(self, "Reset stats", f'Reset all stats for "{klass.name}"?') != QMessageBox.StandardButton.Yes:
            return
        if self.session.current_student:
            self._clear_current()
        self.repo.reset_class_stats(klass.id)
        self._refresh_students()
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
        self.settings.chime_enabled = self.chime_enabled.isChecked()
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
        self.chime_enabled.setChecked(self.settings.chime_enabled)
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
                self.session.current_student, self._pick_kind
            )
        self._update_header()
        self._refresh_leaderboard()

    def _toggle_overlay(self, enabled):
        self.settings.overlay_enabled = enabled
        self.repo.save_settings(self.settings)
        if not enabled:
            self.overlay.hide_overlay()
        elif self.session.current_student:
            self.overlay.monitor_status = self.overlay.show_student(self.session.current_student, self._pick_kind)
        self._update_header()

    def _update_formula(self, *_):
        if not hasattr(self, "scoring_controls"):
            return
        terms = {}
        for key, label in {
            "correct": "correct", "volunteer": "volunteers",
            "incorrect": "incorrect", "skip": "skips",
        }.items():
            effect, points = self.scoring_controls[key]
            sign = "+" if effect.currentText() == "add" else "−"
            terms[key] = f"{sign} ({label} × {points.value():g})"
        score_terms = [
            f"{terms['correct']} ÷ Times Picked",
            terms["volunteer"], terms["skip"], terms["incorrect"],
        ]
        self.formula_preview.setText(
            "Total Points = " + " ".join(terms.values())
            + "\nLeaderboard Score = " + " ".join(score_terms)
        )

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
