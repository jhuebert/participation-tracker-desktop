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
    value TEXT NOT NULL
);

-- Per-class runtime session state (attendance, session skips, last-picked and
-- per-session counters). Mirrors the web v2 ``participationSession`` store.
CREATE TABLE IF NOT EXISTS class_sessions (
    class_id   INTEGER PRIMARY KEY REFERENCES classes(id) ON DELETE CASCADE,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
