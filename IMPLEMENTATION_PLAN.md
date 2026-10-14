# Participation Tracker Desktop — Implementation Plan

**A native Windows desktop app that merges the *Dual Monitor Object Selector*
overlay with the core functionality of the web *Participation Tracker*, backed by
a local SQLite database and shipped as a standalone `.exe`.**

> **Audience:** a fresh coding agent with no prior context. Everything needed to
> build this successfully is in this document. Read it fully before writing code.
> When in doubt, match the **behavior of the reference projects** described here.

---

## 0. TL;DR / Decisions already locked in

| Decision | Choice |
|---|---|
| Language / UI | Python 3.11/3.12 + **PySide6 (Qt 6)** |
| Database | **SQLite** via the standard-library `sqlite3` module |
| Packaging | **PyInstaller** → single-file `.exe` (`--onefile --windowed`) |
| Scope | **Core tracker only**: classes, students, attendance, random/weighted pick, teacher pick, volunteer, correct/incorrect/skip, leaderboard, CSV + JSON import/export, and all scoring/weight settings. **No** PPTX slide viewer, **no** split-screen presentation, **no** student-view web mode. |
| Import sources | Web **JSON backup** *and* web **per-class CSV** |
| Second monitor | The compact topmost overlay box from *Dual Monitor Object Selector*, pinned to the bottom-left of the extended monitor; ESC clears it; falls back to primary. |
| Look & feel | Modern, sleek, custom QSS theme (light "Slate" theme with indigo accent). Do **not** copy the clunky web UI. |

### Project location (create these)

- **New app root (create it):** `C:\Users\Allen\Documents\dev\ParticipationTrackerDesktop\`
- **This plan file:** `C:\Users\Allen\Documents\dev\Dual Monitor Object Selector\IMPLEMENTATION_PLAN.md`
- **Reference projects (read-only, do not modify):**
  - Overlay reference: `C:\Users\Allen\Documents\dev\Dual Monitor Object Selector\app.py` (+ `README.md`)
  - Web tracker reference: `C:\Users\Allen\Documents\dev\Participation Tracker\src\index.html` (the entire web app; 2381 lines)

> If any reference path is missing, re-derive from this document — the relevant
> algorithms and data shapes are reproduced here.

---

## 1. Product summary

The teacher runs the app on their laptop. It shows a modern control window with
four areas (Picker, Leaderboard, Classes, Settings). The teacher selects a class,
marks attendance, and picks students (randomly with fairness weighting, by
teacher choice, or by volunteer). When a student is selected, their **name appears
in a compact, always-on-top box in the bottom-left corner of the extended
(second) monitor** so the class can see who is up — exactly like the standalone
overlay demo. Marking correct/incorrect/skip (or pressing ESC) clears the box.

All classes, students, and lifetime stats live in a single SQLite file created
next to the `.exe` on first launch. The app can import the JSON backups and CSV
exports produced by the current web-based Participation Tracker.

---

## 2. Reference behavior to reproduce (source of truth)

### 2.1 Data model (from the web app)

```
classes = {
  "<ClassName>": {
    "students": {
      "<Student Name>": {
        "picks": int, "correct": int, "incorrect": int,
        "volunteers": int, "skips": int
      }
    }
  }
}
```

### 2.2 Export JSON shape (`ParticipationTracker_Backup.json`)

```json
{
  "app": "Participation Tracker",
  "date": "1/1/2026, 12:00:00 PM",
  "data": {
    "Period 1 - Math": {
      "students": {
        "John Smith": { "picks": 3, "correct": 2, "incorrect": 1, "volunteers": 1, "skips": 0 }
      }
    }
  }
}
```

Import must accept this. The `date` field is informational only. **Note:** the web
backup does **not** contain scoring/weight settings (those live in separate
`localStorage` keys), so settings are *not* imported from JSON.

### 2.3 Per-class CSV export (from the web app)

Header and row order:

```
Rank,Name,Picks,Volunteers,Skips,Correct,Incorrect,Total Participation Points,Leaderboard Score
1,"John Smith",3,1,0,2,1,4,1.33
```

- Names are quoted; may contain commas/quotes → parse with the `csv` module.
- `Rank`, `Total Participation Points`, and `Leaderboard Score` are **derived**;
  ignore them on import (they are recomputed from the raw counters using current
  settings).
- **The CSV does not contain a class name.** The filename is
  `<ClassName>_statistics.csv`. On import, ask the user for the destination class
  name, pre-filling from the filename (strip a trailing `_statistics`).

### 2.4 Settings & defaults (from the web app)

**Weighted selection** (applies to "Pick Random"):

| Setting | Default |
|---|---|
| `weighted_enabled` | true |
| `weight_volunteer_amt` / `_dir` | 30 / `decrease` |
| `weight_correct_amt` / `_dir` | 15 / `decrease` |
| `weight_incorrect_amt` / `_dir` | 10 / `increase` |
| `weight_skip_amt` / `_dir` | 20 / `increase` |

**Participation scoring** (drives leaderboard):

| Setting | Default |
|---|---|
| `scoring_correct_points` / `_effect` | 2 / `add` |
| `scoring_volunteer_points` / `_effect` | 1 / `add` |
| `scoring_incorrect_points` / `_effect` | 1 / `subtract` |
| `scoring_skip_points` / `_effect` | 1 / `subtract` |

**Other:** `skip_limit` = 3 (per-session skips allowed before a student must
answer).

### 2.5 Algorithms (port exactly)

**Participation points** (rounded to 2 decimals):

```
applyEffect(effect, pts, count) = (pts * count) if effect == "add" else -(pts * count)
points = applyEffect(correctEffect, correctPoints, correct)
       + applyEffect(volunteerEffect, volunteerPoints, volunteers)
       + applyEffect(incorrectEffect, incorrectPoints, incorrect)
       + applyEffect(skipEffect, skipPoints, skips)
```

**Leaderboard score:** `0 if picks == 0 else points / picks`.

**Weighted pick** (over the eligible list):

```
base = 100
for name in eligible:
    w = base
    w = applyDir(w, weight_volunteer_dir, weight_volunteer_amt, student.volunteers)
    w = applyDir(w, weight_correct_dir,   weight_correct_amt,   student.correct)
    w = applyDir(w, weight_incorrect_dir, weight_incorrect_amt, student.incorrect)
    w = applyDir(w, weight_skip_dir,      weight_skip_amt,      student.skips)
    weight[name] = max(1, w)
# applyDir: base - amt*count if dir == "decrease" else base + amt*count
# weighted random draw over weight[]; if weighted disabled, uniform random.
```

**Pick rules (`Pick Random`):**

1. Eligible = present students **excluding the last-picked student**.
2. If that leaves nobody (only one student present), fall back to the present
   student(s) with the **fewest lifetime picks** (ties broken randomly).
3. Selected student's `picks += 1`.
4. `last_picked = selection`; broadcast/overlay the name.

**Teacher Pick:** choose any student via a searchable dialog (web shows Present
and Absent groups); `picks += 1`. Does **not** count as a volunteer.

**Volunteer:** choose a present student; `picks += 1` **and** `volunteers += 1`.

**Correct / Incorrect:** increments `correct` or `incorrect` for the current
student, then clears the current selection (and hides the overlay).

**Skip:** permitted only while `session_skips[student] < skip_limit` (when
`skip_limit > 0`); increments `skips`, increments the per-session skip counter,
then clears the current selection.

**Attendance:** on loading a class, every student is present by default; teacher
can toggle, "Select All", "Deselect All". Attendance is **session-only** (not
persisted) — match the web app.

**Skip counters and last-picked are session-only** (reset when loading a class).

### 2.6 Second-monitor overlay (from *Dual Monitor Object Selector*)

Reference implementation facts (see `app.py`):

- Enumerates monitors with Win32 `EnumDisplayMonitors` + `GetMonitorInfoW` via
  `ctypes`; picks the first **non-primary** monitor, else falls back to the
  primary.
- Process is marked **per-monitor DPI aware** so window placement is exact on
  mixed-scale setups.
- The box is a **frameless, topmost** window sized to its text, anchored at the
  **bottom-left** of the monitor's work area with a **24 px margin**.
- ESC in the control window clears the highlight and hides the box.
- Layout is re-detected on every selection.
- A test hook `DUAL_DISPLAY_FAKE_SECONDARY="X,Y,W,H"` overrides detection so the
  placement math can be exercised on a single-monitor machine. **Keep this hook.**
- The control window keeps keyboard focus; the overlay must never steal focus.

---

## 3. Technology & dependencies

**Runtime**

- Python **3.11 or 3.12** (64-bit).
- `PySide6` (Qt 6) — UI. Pin an exact version in `requirements.txt`, e.g.
  `PySide6==6.7.3`.
- Standard library only for everything else: `sqlite3`, `csv`, `json`,
  `ctypes`, `logging`, `pathlib`, `dataclasses`, `random`.

**Dev / build**

- `pyinstaller` (pin, e.g. `pyinstaller==6.11.0`)
- `pytest`

**Why PySide6:** modern themeable UI via QSS, native Windows rendering, robust
multi-monitor support, and it interoperates with the existing `ctypes` Win32
monitor code.

**`requirements.txt`**

```
PySide6==6.7.3
```

**`requirements-dev.txt`**

```
-r requirements.txt
pyinstaller==6.11.0
pytest==8.3.3
```

---

## 4. Project layout

Create exactly this structure under
`C:\Users\Allen\Documents\dev\ParticipationTrackerDesktop\`:

```
ParticipationTrackerDesktop/
├─ README.md                     # how to run & build
├─ requirements.txt
├─ requirements-dev.txt
├─ pyproject.toml                # optional: pytest config, tooling
├─ build.ps1                     # one-command PyInstaller build
├─ ParticipationTracker.spec     # PyInstaller spec file
├─ assets/
│  └─ icon.ico                   # app/exe icon (see §12.5)
├─ src/
│  └─ participation_tracker/
│     ├─ __init__.py             # __version__
│     ├─ __main__.py             # `python -m participation_tracker`
│     ├─ main.py                 # bootstrap: DPI, QApplication, theme, window
│     ├─ config.py               # paths (app dir, DB, log), constants
│     ├─ logging_setup.py        # file + console logging
│     ├─ models.py               # dataclasses: Class, Student, Settings
│     ├─ monitors.py             # ctypes Win32 monitor enumeration + target picker
│     ├─ overlay.py              # OverlayWindow (Qt frameless topmost box)
│     ├─ db/
│     │  ├─ __init__.py
│     │  ├─ schema.sql           # CREATE TABLE statements
│     │  ├─ database.py          # Database: connect, migrations, tx helper
│     │  └─ repository.py        # Repository: all CRUD/queries
│     ├─ services/
│     │  ├─ __init__.py
│     │  ├─ scoring.py           # participation points + leaderboard score
│     │  ├─ picker.py            # weighted/uniform selection (injectable RNG)
│     │  ├─ session.py           # Session: attendance, skips, current, last
│     │  ├─ importer.py          # JSON + CSV import
│     │  └─ exporter.py          # JSON + CSV export
│     └─ ui/
│        ├─ __init__.py
│        ├─ theme.py             # palette tokens + QSS stylesheet
│        ├─ main_window.py       # shell: sidebar nav + stacked pages + header
│        ├─ pages/
│        │  ├─ picker_page.py
│        │  ├─ leaderboard_page.py
│        │  ├─ classes_page.py
│        │  └─ settings_page.py
│        ├─ dialogs/
│        │  ├─ teacher_pick_dialog.py
│        │  ├─ volunteer_dialog.py
│        │  ├─ import_dialog.py       # choose replace/merge + class name for CSV
│        │  └─ class_create_dialog.py # or inline form on Classes page
│        └─ widgets/
│           ├─ stat_card.py
│           ├─ toast.py
│           ├─ section_header.py
│           └─ student_button.py
└─ tests/
   ├─ conftest.py
   ├─ test_scoring.py
   ├─ test_picker.py
   ├─ test_repository.py
   ├─ test_importer.py
   ├─ test_exporter.py
   └─ fixtures/
      ├─ backup_sample.json
      └─ Period_1_math_statistics.csv
```

**Entry point:** `src/participation_tracker/main.py` with a `main()` function.
`__main__.py` calls it. The PyInstaller spec points at `src/participation_tracker/main.py`
and adds `src` to the search path.

---

## 5. Database design

### 5.1 Location ("next to the exe")

In `config.py`:

```python
import os, sys
from pathlib import Path

def app_dir() -> Path:
    if getattr(sys, "frozen", False):          # PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]  # project root when run from source

DB_FILENAME = "participation_tracker.db"
LOG_FILENAME = "participation_tracker.log"

def data_dir() -> Path:
    # Prefer the exe's folder; fall back to %LOCALAPPDATA% if not writable.
    d = app_dir()
    try:
        probe = d / ".write_test"
        probe.write_text("")
        probe.unlink()
        return d
    except OSError:
        fallback = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ParticipationTracker"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

def db_path() -> Path: return data_dir() / DB_FILENAME
def log_path() -> Path: return data_dir() / LOG_FILENAME
```

- Use `sys.executable` for frozen apps (PyInstaller `--onefile` extracts code to a
  temp dir, so `__file__` is wrong; `sys.executable` is the real `.exe` path).
- If the folder is read-only (e.g. installed under `Program Files`), fall back to
  `%LOCALAPPDATA%\ParticipationTracker` and show a one-time info toast.

### 5.2 Schema (`db/schema.sql`, version 1)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS students (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id   INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    picks      INTEGER NOT NULL DEFAULT 0,
    correct    INTEGER NOT NULL DEFAULT 0,
    incorrect  INTEGER NOT NULL DEFAULT 0,
    volunteers INTEGER NOT NULL DEFAULT 0,
    skips      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (class_id, name)
);

CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL          -- JSON-encoded scalar
);
```

### 5.3 `Database` (db/database.py)

- `Database(path)`: opens `sqlite3.connect(str(path), detect_types=..., isolation_level=None)`
  and sets `conn.row_factory = sqlite3.Row`, `PRAGMA foreign_keys=ON`,
  `PRAGMA journal_mode=WAL`.
- `initialize()`: runs `schema.sql` idempotently; reads `schema_version`; if the
  table is empty, insert `1`; run ordered `MIGRATIONS` (list of callables) for any
  version < current. Version 1 has no migrations.
- `transaction()`: context manager that issues `BEGIN`/`COMMIT`/`ROLLBACK`
  (since `isolation_level=None` gives manual control).

### 5.4 `Repository` (db/repository.py)

Dataclass-returning methods, all class/student operations wrapped in
transactions as needed:

- `list_classes() -> list[Class]` (ordered by name)
- `get_class_by_name(name) -> Class | None`
- `create_class(name: str, students: list[str]) -> Class`
  - Trim; de-duplicate names case-insensitively preserving first occurrence;
    skip blanks; raise `ValueError` if name or resulting student list is empty.
- `rename_class(class_id, new_name)` (optional nice-to-have)
- `delete_class(class_id)`
- `list_students(class_id) -> list[Student]` (ordered by name)
- `add_student(class_id, name)` / `delete_student(student_id)` (optional)
- `apply_event(class_id, student_name, field: Literal["picks","correct","incorrect","volunteers","skips"], delta: int = 1)`
  — atomic `UPDATE ... SET field = field + :delta`.
- `set_stats(class_id, name, stats_dict)` — used by import.
- `reset_class_stats(class_id)` — zeroes all five counters.
- `replace_all(classes: dict)` — delete all classes; insert from dict.
- `merge_all(classes: dict)` — upsert (see §7.1 for exact semantics).
- Settings: `get_settings() -> Settings` and `save_settings(Settings)`.
  Store each field under a key with a JSON-encoded value; unknown keys are
  ignored and missing keys fall back to defaults.

`models.py`:

```python
@dataclass
class Student:
    id: int; class_id: int; name: str
    picks: int = 0; correct: int = 0; incorrect: int = 0
    volunteers: int = 0; skips: int = 0

@dataclass
class Class:
    id: int; name: str; student_count: int = 0

@dataclass
class Settings:
    skip_limit: int = 3
    weighted_enabled: bool = True
    weight_volunteer_amt: int = 30; weight_volunteer_dir: str = "decrease"
    weight_correct_amt: int = 15;   weight_correct_dir: str = "decrease"
    weight_incorrect_amt: int = 10; weight_incorrect_dir: str = "increase"
    weight_skip_amt: int = 20;      weight_skip_dir: str = "increase"
    scoring_correct_points: float = 2.0;   scoring_correct_effect: str = "add"
    scoring_volunteer_points: float = 1.0; scoring_volunteer_effect: str = "add"
    scoring_incorrect_points: float = 1.0; scoring_incorrect_effect: str = "subtract"
    scoring_skip_points: float = 1.0;      scoring_skip_effect: str = "subtract"
    overlay_enabled: bool = True
```

---

## 6. Services (pure logic — must be unit-tested)

### 6.1 `services/scoring.py`

```python
def participation_points(stats, settings) -> float: ...   # round(x, 2)
def leaderboard_score(stats, settings) -> float: ...       # 0 if picks == 0
```

`stats` is a `Student` or any object/dict exposing the five counters. Implement
with a small `_get(stats, "correct")` helper accepting both.

### 6.2 `services/picker.py`

```python
def pick_random(present: set[str], students: dict[str, Student],
                settings: Settings, last_picked: str | None,
                rng: random.Random | None = None) -> str:
    """Return the chosen student name. Raises ValueError if nobody eligible."""
```

- Build eligible list per §2.5, using the injected `rng` (default
  `random.Random()`) so tests are deterministic.
- Implement `_weight_for(student, settings)` and a weighted draw; uniform draw
  when `weighted_enabled` is False.
- Raise `ValueError("no students present")` when `present` is empty.

### 6.3 `services/session.py`

```python
class Session:
    """Per-class, in-memory runtime state. Not persisted."""
    class_id: int | None
    present: set[str]
    session_skips: dict[str, int]
    current_student: str | None
    last_picked: str | None
    def load_class(self, klass, students): ...  # all present, counters reset
    def toggle_attendance(self, name, present: bool): ...
    def select_all(self, names): ...
    def deselect_all(self): ...
    def can_skip(self, name, skip_limit) -> bool: ...
    def record_skip(self, name): ...
    def clear_current(self): ...
```

### 6.4 `services/importer.py`

- `parse_backup_json(text: str) -> dict[str, dict]`
  - `json.loads`; assert `obj.get("app") == "Participation Tracker"` and
    `isinstance(obj.get("data"), dict)`; else raise `ImportError` with a clear
    message.
  - Normalize: for each class → students mapping, for each student coerce the
    five counters to non-negative ints (missing → 0).
- `parse_class_csv(text: str) -> list[tuple[str, dict]]`
  - `csv.reader`; verify the header contains at least `Name`, and the counter
    columns; map columns by header name (order-independent but match the web
    order when exporting). Return `[(name, {picks, correct, incorrect, volunteers, skips})]`.
  - Ignore `Rank`, `Total Participation Points`, `Leaderboard Score`.
- Return clear, user-facing error messages; never crash on malformed input.

### 6.5 `services/exporter.py`

- `to_backup_json(classes: dict) -> str` — reproduce the web shape exactly
  (`app`, `date`, `data`), `json.dumps(..., indent=2)`. `date` = current locale
  date string (informational).
- `to_class_csv(klass_name, students, settings) -> str` — reproduce the web
  header/rows exactly, computing `Total Participation Points` and
  `Leaderboard Score` with `scoring.py`; quote names via the `csv` module.
- File-writing helpers `export_backup(path)`, `export_csv(path, ...)`.

---

## 7. Import UX & semantics

### 7.1 JSON backup

After parsing, show an `ImportDialog` with two modes:

- **Replace all data** (default, matches web behavior): after a
  destructive-action confirmation ("This permanently deletes all existing
  classes"), `repository.replace_all(data)`.
- **Merge:** for each class: create if missing; for each student: insert if
  missing, otherwise **overwrite** that student's five counters with the imported
  values. Add a short explanatory line in the dialog.

Always report a summary toast: `Imported N classes, M students`.

### 7.2 CSV

1. Parse the file.
2. Ask for the destination class name (pre-fill by stripping a trailing
   `_statistics` from the filename, and replacing `_` with spaces if desired).
3. Ask Replace/Merge if the class already exists; otherwise create it.
4. Insert rows.

Both import flows go through the **Classes page** and/or a **File ▸ Import**
menu. Use `QFileDialog` with filters `*.json`, `*.csv`, `*.txt`.

---

## 8. Second-monitor overlay (port + Qt adaptation)

### 8.1 `monitors.py` (port from the reference, stdlib only)

Reproduce the reference almost verbatim — it is proven and dependency-free:

- `enable_dpi_awareness()` — kept for reference but **see §8.4**: when using Qt,
  let Qt manage DPI awareness and only call this in non-Qt contexts/tests.
- `RECT`, `MONITORINFO`, `MONITORENUMPROC` ctypes structures.
- `get_monitors() -> list[Monitor]` — dataclass
  `Monitor(rect: tuple[int,int,int,int], work: tuple[int,int,int,int], primary: bool)`.
- `get_display_target(fallback_w, fallback_h) -> tuple[Monitor, bool]`:
  - honors `DUAL_DISPLAY_FAKE_SECONDARY="X,Y,W,H"` (testing hook),
  - returns the first non-primary monitor (extended) if present,
  - else the primary, with `extended_found=False`.
- Keep all coordinate math in **physical pixels**.

### 8.2 `overlay.py` — `OverlayWindow(QWidget)`

Requirements:

- Frameless, always-on-top, tool window, **does not accept focus**, shown without
  activation:

  ```python
  self.setWindowFlags(
      Qt.FramelessWindowHint
      | Qt.WindowStaysOnTopHint
      | Qt.Tool
      | Qt.WindowDoesNotAcceptFocus
  )
  self.setAttribute(Qt.WA_ShowWithoutActivating, True)
  ```

- Content: a horizontal row — optional volunteer icon `🙋` (only when the
  selection was a volunteer) + the student name in a large bold font. A small
  colored frame/gradient provides a "minimal border" like the reference. Use the
  overlay palette (see §9). Size is derived from the text (`sizeHint`) plus ~2 px
  border, similar to the reference box.
- `show_student(name: str, is_volunteer: bool) -> None`:
  1. Re-detect the target monitor (`get_display_target(...)`).
  2. Resize to content, then position at `(work.left + 24, max(work.top + 24, work.bottom - height - 24))`.
  3. `show()` / `raise_()`; **do not** activate.
  4. Enforce exact physical placement via Win32 `MoveWindow` on the overlay HWND
     (`int(self.winId())`) — mirroring the reference's `_force_position`. Do this
     after a `QTimer.singleShot(30, ...)` so the window is mapped.
  5. Return the monitor used so the UI can show the status line
     ("Showing on extended display" vs "No extended display — showing here").
- `hide_overlay()` — hides the box (used on clear/mark/reset/ESC).
- Respect `settings.overlay_enabled` and a global "Overlay: on/off" toggle.
- Never steal focus from the control window: after showing, call
  `main_window.activateWindow()` / `raise_()`.

### 8.3 Wiring

- Overlay instance is owned by `MainWindow`. Call `show_student(name, is_volunteer)`
  whenever a student is selected (random/teacher/volunteer) and `hide_overlay()`
  whenever the selection is cleared (correct/incorrect/skip/ESC/new class/reset).
- ESC on the main window clears the current selection and hides the overlay.
  Register it as a `QShortcut` on the main window.

### 8.4 DPI handling with Qt

- **Do not** fight Qt's DPI management. In `main.py`, before creating
  `QApplication`:

  ```python
  from PySide6.QtCore import Qt
  from PySide6.QtGui import QGuiApplication
  QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
      Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
  )
  ```

  Qt 6 sets per-monitor-v2 awareness on Windows by default.
- Place the overlay primarily with Win32 `MoveWindow` in physical pixels (obtained
  from `get_display_target`), which sidesteps logical-vs-physical scaling on
  mixed-DPI multi-monitor setups. Keep a Qt `setGeometry` call as a fallback for
  the single-monitor case.
- **Verify on real hardware** with two monitors at different scale factors; use
  `DUAL_DISPLAY_FAKE_SECONDARY` while developing on one monitor to sanity-check
  the math.

---

## 9. Look & feel (modern, sleek — independent of the web UI)

### 9.1 Palette tokens (`ui/theme.py`)

```python
COLORS = {
    "bg":         "#F8FAFC",
    "surface":    "#FFFFFF",
    "surface_alt":"#F1F5F9",
    "border":     "#E2E8F0",
    "text":       "#0F172A",
    "text_muted": "#64748B",
    "accent":     "#4F46E5",   # indigo
    "accent_hover":"#4338CA",
    "accent_soft":"#EEF2FF",
    "success":    "#10B981",
    "danger":     "#EF4444",
    "warning":    "#F59E0B",
    "info":       "#0EA5E9",
    "overlay_bg": "#6D28D9",   # overlay box fill
    "overlay_fg": "#F8FAFC",
}
FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", sans-serif'
```

### 9.2 Design language

- Single global QSS stylesheet applied to `QApplication` from `theme.py`.
- **Navigation rail** on the left (~220 px): app title/logo, four nav items
  (Picker, Leaderboard, Classes, Settings) with hover/active states, and an
  overlay on/off switch at the bottom. Content on the right in a
  `QStackedWidget`.
- **Header bar** on the right: current class selector (`QComboBox`, styled),
  attendance summary chip (e.g. "18 / 22 present"), and a compact status pill for
  the overlay target.
- **Cards**: `QFrame` with `objectName="Card"`, white background, 1 px border,
  12–14 px radius, and a subtle `QGraphicsDropShadowEffect`.
- **Buttons**: primary (accent fill), secondary (surface + border), and
  semantic (success/danger/warning/info). Rounded (8–10 px), generous padding,
  hand cursor, hover/pressed states. Large action buttons for pick/volunteer/
  correct etc.
- **Stat cards**: six cards in a responsive grid — Total Students, Present,
  Total Picks, Correct, Volunteers, Skips — big number + muted label.
- **Selected-student display**: a prominent centered card with the current name
  (or "Ready to pick!"). Volunteers show a 🙋 badge.
- **Attendance**: a scrollable grid of toggle "chips" (name + check), green when
  present, grey when absent, with Select All / Deselect All.
- **Leaderboard**: styled `QTableView`/`QTableWidget` — sortable, zebra rows,
  colored Correct (green) / Incorrect (red), bold score column. Export CSV and
  Reset buttons.
- **Dialogs** (Teacher Pick, Volunteer): `QDialog` with a search field (teacher
  pick), a scrollable grid of student buttons grouped Present / Absent, hover
  highlight, and clear primary action. Volunteer dialog lists present students.
- **Toast**: lightweight top-center notification widget (auto-dismiss ~3 s) for
  success/error/info messages.
- Use emoji/simple icons (🎲 🍎 🙋 ✓ ✗ ⏭️ 📤 📥 📊 🗑️ ⚙️) to match the web app's
  affordances, rendered via font; keep them consistent.

### 9.3 Interaction & keyboard

- `Space` — Pick Random (when Picker page focused and a class is loaded).
- `Esc` — clear current selection + hide overlay.
- `Ctrl+1..4` — switch pages.
- All destructive actions (delete class, reset leaderboard, replace-import)
  require confirmation dialogs.

---

## 10. Build → single `.exe`

### 10.1 PyInstaller spec (`ParticipationTracker.spec`)

- Entry: `src/participation_tracker/main.py`; `pathex=["src"]`.
- `datas`: include `src/participation_tracker/db/schema.sql` and
  `assets/icon.ico`.
- `console=False`, `name="Participation Tracker"`,
  `icon="assets/icon.ico"`.
- Exclude unused Qt modules to reduce size (e.g. `QtWebEngineCore`,
  `QtQuick`, `QtQml`, `Qt3D*`, `QtMultimedia`, `QtCharts`, `QtNetwork` only if
  genuinely unused). Rely on PyInstaller's PySide6 hooks; add `--collect-submodules`
  only if a module is missing at runtime.
- Recommend `--onefile` for a true "standard exe". Note the trade-off: onefile
  has a slower first launch (it unpacks to `%TEMP%`); also provide an `--onedir`
  switch in `build.ps1` for faster startup if desired.

### 10.2 `build.ps1`

```powershell
param([switch]$Onedir)
$ErrorActionPreference = "Stop"
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean `
    --distpath dist --workpath build `
    $(if ($Onedir) { "-D" } else { "-F" }) `
    ParticipationTracker.spec
Write-Host "Built -> dist\Participation Tracker.exe"
```

### 10.3 Runtime notes for the frozen app

- **Logging:** with `--windowed` there is no console. Configure `logging` in
  `logging_setup.py` to write `participation_tracker.log` (via `config.log_path()`)
  at INFO level, plus an in-memory deque for a future "View log" action. Install
  `sys.excepthook` to log uncaught exceptions and show a `QMessageBox` so failures
  are visible.
- Verify the DB is created **next to the exe** on first run; confirm the
  `%LOCALAPPDATA%` fallback works when the folder is read-only.
- No external assets are fetched at runtime (unlike the web app's JSZip CDN).

---

## 11. Implementation milestones (do in this order)

1. **Scaffold & bootstrap** — create the tree, `requirements.txt`, `config.py`,
   `logging_setup.py`, `main.py` that opens an empty themed `QMainWindow`. Confirm
   it runs: `python -m participation_tracker`.
2. **Database layer** — `schema.sql`, `Database`, `Repository`, `models.py`,
   settings. Unit-test `Repository` against a temp DB file.
3. **Pure services** — `scoring.py`, `picker.py`, `importer.py`, `exporter.py`.
   Write all unit tests (fixtures included) **before** wiring UI. These are the
   highest-risk correctness areas.
4. **Core UI shell** — sidebar nav, stacked pages, theme QSS, header, toasts.
5. **Picker page** — class selector, attendance chips, stat cards, current-student
   display, all action buttons, and the pick/skip/answer logic using `Session` +
   `Repository` + `services`.
6. **Dialogs** — Teacher Pick and Volunteer.
7. **Leaderboard page** — table + CSV export + reset.
8. **Classes page** — create/delete class, import/export (JSON + CSV) with the
   import dialog.
9. **Settings page** — skip limit, weighted selection, participation scoring with
   live formula preview; persistence.
10. **Overlay** — `monitors.py`, `overlay.py`, wiring + ESC, fallback handling,
    `DUAL_DISPLAY_FAKE_SECONDARY` hook. Test on one and two monitors.
11. **Polish** — keyboard shortcuts, empty states, error handling, confirmations,
    icon, README.
12. **Package** — spec + `build.ps1`; build and smoke-test the `.exe` on a clean
    folder (verify DB creation, import, overlay, single-monitor fallback).

---

## 12. Testing strategy

### 12.1 Automated (`pytest`)

- `test_scoring.py` — participation points and leaderboard score for all
  effect/point combinations; `picks == 0 → 0`; rounding to 2 decimals.
- `test_picker.py` — with a seeded `random.Random`:
  - weighted vs uniform,
  - last-picked exclusion,
  - single-present-student fallback to fewest picks,
  - min-weight clamp at 1,
  - `ValueError` when nobody present.
- `test_repository.py` — create/list/delete class, duplicate student handling,
  `apply_event` atomic increments, `reset_class_stats`, `replace_all`,
  `merge_all`, settings round-trip, migration idempotency.
- `test_importer.py` — parse the sample backup JSON and CSV fixtures; reject
  malformed JSON (`app` wrong / missing `data`) and malformed CSV header; handle
  quoted names with commas and escaped quotes; missing counters default to 0.
- `test_exporter.py` — JSON round-trips through the importer; CSV header/row
  format matches the web app exactly (compare to fixture string).

### 12.2 Fixtures to create

- `tests/fixtures/backup_sample.json` — two classes, several students with mixed
  counters, including a name with a comma.
- `tests/fixtures/Period_1_math_statistics.csv` — matching the web header, with a
  quoted comma-name.

### 12.3 Manual checklist (record results in the README or a scratch file)

- [ ] First run creates `participation_tracker.db` next to the exe.
- [ ] Create a class with many students; restart the app; class persists.
- [ ] Attendance toggles update the "present" stat.
- [ ] Pick Random respects weighting and never repeats the last pick.
- [ ] Teacher Pick and Volunteer update the right counters.
- [ ] Correct/Incorrect/Skip clear the display and hide the overlay.
- [ ] Skip limit blocks further skips after N per session.
- [ ] Leaderboard matches hand-computed points/scores; sorting works.
- [ ] CSV export matches the web format; importing it back reproduces stats.
- [ ] JSON export → import (replace) reproduces all classes/stats exactly.
- [ ] Import a real backup from the web app; verify counts.
- [ ] Overlay appears bottom-left of the **second** monitor, stays on top, never
      steals focus; ESC clears it.
- [ ] Single-monitor fallback shows the overlay on the primary with a notice.
- [ ] `DUAL_DISPLAY_FAKE_SECONDARY` hook works.
- [ ] App is usable maximized and at ~1024 px width; DPI scaling looks correct.

---

## 13. Edge cases & rules

- **Duplicate student names** in one class collapse to one (web behavior uses
  object keys). On class creation, de-duplicate case-insensitively and note it.
- **Whitespace/blank names** are trimmed and skipped.
- **Unique class names** — creating an existing class name is an error (match web
  "Class exists"); offer to open/merge instead.
- **CSV names with commas/quotes** must survive round-trips (use `csv` module,
  never manual string concatenation).
- **Missing counters** in imported data default to 0; negative values are clamped
  to 0.
- **No students present** → Pick Random/Volunteer show an error toast.
- **Read-only install dir** → DB falls back to `%LOCALAPPDATA%` + notice.
- **Monitors added/removed at runtime** → re-detect on every selection.
- **Overlay disabled** → selection still works; only the second-monitor box is
  suppressed.
- **Large classes** → attendance grid and dialogs must scroll.
- **DB corruption / locked** → catch `sqlite3.Error`, log, show a friendly dialog.

---

## 14. Distribution notes

- Ship the built `dist\Participation Tracker.exe` plus (optionally) a short
  `README.txt`. The `.db` file is created on first run and should **not** be
  bundled.
- Windows SmartScreen may warn about an unsigned exe; document that the user can
  choose "More info → Run anyway" (or sign it later).
- Keep the app fully offline — no network calls anywhere in the code.

---

## 15. Definition of done

1. `python -m participation_tracker` runs from source and the built
   `Participation Tracker.exe` runs standalone.
2. All §11 milestones complete; all §12.1 tests pass (`pytest` green).
3. Core tracker feature parity with the web app's **non-slide** functionality,
   including scoring and weighted-selection settings.
4. SQLite DB is created next to the exe on first run (with `%LOCALAPPDATA%`
   fallback) and persists all classes/students/stats/settings.
5. JSON backup and per-class CSV imports from the web app work and round-trip.
6. The second-monitor overlay behaves as specified, with single-monitor fallback
   and the `DUAL_DISPLAY_FAKE_SECONDARY` test hook.
7. UI is modern and sleek per §9 (sidebar nav, cards, custom theme) — visually
   distinct from the web app.
8. `README.md` documents running, building, importing, and the manual checklist.

---

## 16. Assumptions & optional follow-ups

- **Assumption:** attendance, session skips, and last-picked are session-only, as
  in the web app. Not persisted.
- **Assumption:** scoring/weight settings are global (one set for all classes), as
  in the web app.
- **Optional later:** per-class settings, attendance history, a "student
  presentation" full-window mode on the second monitor (larger than the compact
  box), auto-update, code signing, and CSV export of all classes at once.
- **Explicitly out of scope:** PPTX slide rendering, split-screen presentation,
  and the browser-based student view.
