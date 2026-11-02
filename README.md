# Participation Tracker Desktop

A native, offline Windows app for managing classes, student participation, weighted random selection, attendance, leaderboards, and a compact second-monitor overlay. Data is stored in SQLite locally. PPTX viewer and web student mode are intentionally out of scope.

## Requirements

- Python 3.11+ (64-bit) and Windows for the monitor overlay.
- Install runtime requirements: `python -m pip install -r requirements.txt`
- Run from the project root:

```powershell
$env:PYTHONPATH = "src"
python -m participation_tracker
```

The database `participation_tracker.db` and log are created next to the project root while running from source. Frozen builds store them next to the executable, falling back to `%LOCALAPPDATA%\ParticipationTracker` if needed.

## Data

Create a class on the Classes page, one student per line. Lifetime stats and settings persist in SQLite. JSON backups from the web app and per-class CSV files are supported. JSON can replace all data or merge (matching student counters are overwritten); CSV asks for its destination class. Use File → Import/Export or the Classes page. Export CSV from the Leaderboard page.

## Features ported from the TypeScript v2 rewrite

The Desktop app incorporates several capabilities added in the web v2 rewrite:

- **Roster editing** — each class on the Classes page has an **Edit** action to rename the class and to add, rename, or remove students. Removals require confirmation and discard that student's stats.
- **Persistent sessions** — attendance, per-session skip usage, the last-picked student, and per-session counters are saved per class (a `class_sessions` table) and restored on the next launch. Use **Start new session** on the Picker page to reset a class period (everyone present, skips and session counters cleared) and **Reset session skips** to clear only skip usage.
- **Richer pick dialogs** — Teacher Pick and Volunteer dialogs show each student's *session* tallies (picks / correct / incorrect / volunteers / skips) and mark the **last**-picked student.
- **Settings in backups** — JSON backups include an optional, backward-compatible `settings` block (skip limit, scoring, weights, overlay). Older backups without it still import; importing a backup that has it applies those settings.

## Build

```powershell
.\build.ps1
```

For a faster-starting folder build use `.\build.ps1 -Onedir`. The default is a single-file, windowed executable. Runtime files remain local and no network calls are made. Windows SmartScreen may warn for an unsigned executable.

The Windows app icon comes from `assets/student_raising_hand.png`. To regenerate the multi-size `assets/icon.ico` after changing that source image, run `python tools/make_icon.py` (requires the dev dependencies).

> Build compatibility: the implementation environment has Python 3.14 only, so this checkout pins PySide6 6.12.0 and PyInstaller 6.16.0. For a Python 3.12 toolchain you can use the plan's older pinned versions (PySide6 6.7.3 / PyInstaller 6.11.0).

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest
```

## Manual checklist

- [ ] Create a class, restart, and verify it persists.
- [ ] Toggle attendance, pick random, teacher-pick, and volunteer.
- [ ] Edit a class: rename it, add / rename / remove students; stats follow a rename and are discarded on removal.
- [ ] Restart the app and verify attendance, session skips, last-picked, and session counters are restored per class.
- [ ] Start new session resets attendance/skips/counters; Reset session skips clears only skips.
- [ ] Teacher Pick / Volunteer dialogs show session tallies and mark the last-picked student.
- [ ] Correct / incorrect / skip clear the selection; skip limit is enforced.
- [ ] A pick is only counted once Correct / Incorrect / Skip is marked, so Esc clears the selection without adding to the pick count.
- [ ] Check leaderboard calculations and CSV export/import round trips.
- [ ] JSON export → replace import reproduces all classes and stats, and carries settings (skip limit, scoring, weights).
- [ ] The Leaderboard checkbox can show all students' Rank, Name, Total Points, and Score centered on the extended display; unchecking it or pressing Esc dismisses the summary.
- [ ] Overlay appears on the extended display, stays topmost, and does not steal focus.
- [ ] The overlay shows the pick source icon before the student's name: 🎲 random, 🍎 teacher pick, 🙋 volunteer.
- [ ] A chime plays when a student is picked; the Settings page can silence it.
- [ ] Long student names display in full in the overlay box (also on scaled displays), shrinking only if the name would not fit the screen.
- [ ] Resize the window to a quarter of the main monitor's width: the page title shrinks but stays visible, the nav rail collapses to icons (hover for names), and every page stays usable next to a full-screen app.
- [ ] Settings: the values sit on a panel matching the attendance area, add/subtract and increase/decrease are color-coded, the spin arrows stay visible, and nothing is cut off at any width (rows stack when narrow, Save stays on screen).
- [ ] On the Classes page, class cards keep their full height and scroll vertically rather than clipping names, student counts, or action buttons.
- [ ] On a horizontally scrolled Leaderboard, Rank and Name remain fixed while statistic columns move.
- [ ] The Leaderboard opens with Rank 1 at the top, increasing to the lowest-ranked student.
- [ ] Single-monitor fallback and `DUAL_DISPLAY_FAKE_SECONDARY="1920,0,1920,1080"` work.
- [ ] Review scaled multi-monitor placement on real hardware; Qt's DPI awareness can vary by Windows/Qt build.
