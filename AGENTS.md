# Participation Tracker Desktop — Agent Guide

## Project overview

Participation Tracker is an offline-first Windows desktop app built with Python 3.11+ and PySide6. It supports classes, student participation, weighted random selection, attendance, leaderboards, CSV/JSON import-export, a second-monitor overlay, and a local SQLite database.

## Architecture

- Application entry point: `src/participation_tracker/main.py`.
- PySide6 pages and dialogs: `src/participation_tracker/ui/`.
- Domain/data models: `src/participation_tracker/models.py`.
- SQLite schema, migrations, and persistence: `src/participation_tracker/db/`.
- Reusable business logic: `src/participation_tracker/services/`.
- Display enumeration and overlay: `monitors.py` and `overlay.py`.
- Packaging: `ParticipationTracker.spec` and `build.ps1`.
- Static assets bundled with the app: `assets/`.

Keep UI orchestration in the UI layer, persistence behind `Repository`, and reusable business rules in services. Avoid duplicating calculations or persistence behavior in widgets.

## Engineering expectations

- Follow established patterns and Python best practices: clear names, type hints where useful, small focused functions, and errors handled at the appropriate boundary.
- Prefer simple, DRY solutions. Reuse existing services, widgets, theme tokens, and repository methods rather than introducing parallel implementations.
- Preserve offline behavior and existing user data. Do not delete, replace, migrate, or reset databases or user files unless explicitly requested.
- Keep the desktop UI responsive: do not block the Qt event loop for playback, I/O, or other long-running work. Keep keyboard access, resize behavior, and accessibility in mind.
- Keep visual styling consistent through `ui/theme.py`; use responsive layouts rather than fixed dimensions that clip at narrow sizes.
- Keep runtime dependencies intentional and update packaging/configuration when assets or dependencies change.
- Do not commit generated executables, build directories, local databases, logs, or caches. Follow `.gitignore`; commit required source assets such as icons and bundled sound files.

## Validation

From the project root, run:

```powershell
$env:PYTHONPATH = "src"
python -m pytest
```

Build the Windows executable with:

```powershell
.\build.ps1
```

For UI changes, verify the relevant page at normal and compact window sizes. For monitor-overlay changes, test both the single-monitor fallback and `DUAL_DISPLAY_FAKE_SECONDARY="1920,0,1920,1080"` when practical.

## Keep this guide current

When work establishes a new shared pattern, architectural boundary, build step, or testing convention, update this `AGENTS.md` in the same change. Keep guidance concise and generally applicable; remove or revise stale instructions as the project evolves.
