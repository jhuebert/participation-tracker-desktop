"""SQLite connection management + schema migrations."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
CURRENT_VERSION = 2


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add the per-class session store introduced for persistent sessions.

    ``schema.sql`` already declares the table with ``IF NOT EXISTS`` and runs on
    every launch, so this is primarily a version bump for existing databases.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS class_sessions (
            class_id   INTEGER PRIMARY KEY REFERENCES classes(id) ON DELETE CASCADE,
            data       TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


# Ordered migration callables: index 0 migrates v1 -> v2, etc.
MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_migrate_v1_to_v2]


def _read_schema() -> str:
    """Load schema.sql, working both from source and from a frozen bundle."""
    try:
        return SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError:
        # PyInstaller collects it via datas under participation_tracker/db/.
        import sys

        base = getattr(sys, "_MEIPASS", None)
        if base:
            alt = Path(base) / "participation_tracker" / "db" / "schema.sql"
            return alt.read_text(encoding="utf-8")
        raise


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None  # manual BEGIN/COMMIT
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._in_transaction = False

    def initialize(self) -> None:
        self.conn.executescript(_read_schema())
        cur = self.conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cur.fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (CURRENT_VERSION,)
            )
            return

        version = int(row["version"])
        while version < CURRENT_VERSION:
            migration = MIGRATIONS[version - 1]
            log.info("Migrating database from v%s to v%s", version, version + 1)
            with self.transaction():
                migration(self.conn)
                self.conn.execute("UPDATE schema_version SET version = ?", (version + 1,))
            version += 1

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        if self._in_transaction:
            # Re-entrant: participate in the outer transaction.
            yield self.conn
            return
        self.conn.execute("BEGIN")
        self._in_transaction = True
        try:
            yield self.conn
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")
        finally:
            self._in_transaction = False

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:  # pragma: no cover
            pass
