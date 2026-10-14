"""All class/student/settings CRUD and queries."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Iterable, Literal

from ..models import COUNTER_FIELDS, Class, Settings, Student, default_settings
from .database import Database

log = logging.getLogger(__name__)

CounterField = Literal["picks", "correct", "incorrect", "volunteers", "skips"]


def _dedupe_students(names: Iterable[str]) -> list[str]:
    """Trim, drop blanks, and de-duplicate case-insensitively."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in names:
        name = (raw or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------- classes

    def list_classes(self) -> list[Class]:
        rows = self.db.execute(
            """
            SELECT c.id, c.name, COUNT(s.id) AS student_count
            FROM classes c
            LEFT JOIN students s ON s.class_id = c.id
            GROUP BY c.id, c.name
            ORDER BY c.name COLLATE NOCASE
            """
        ).fetchall()
        return [Class(id=r["id"], name=r["name"], student_count=r["student_count"]) for r in rows]

    def get_class_by_name(self, name: str) -> Class | None:
        row = self.db.execute(
            """
            SELECT c.id, c.name, COUNT(s.id) AS student_count
            FROM classes c
            LEFT JOIN students s ON s.class_id = c.id
            WHERE c.name = ?
            GROUP BY c.id, c.name
            """,
            (name,),
        ).fetchone()
        if row is None:
            return None
        return Class(id=row["id"], name=row["name"], student_count=row["student_count"])

    def get_class(self, class_id: int) -> Class | None:
        row = self.db.execute(
            """
            SELECT c.id, c.name, COUNT(s.id) AS student_count
            FROM classes c
            LEFT JOIN students s ON s.class_id = c.id
            WHERE c.id = ?
            GROUP BY c.id, c.name
            """,
            (class_id,),
        ).fetchone()
        if row is None:
            return None
        return Class(id=row["id"], name=row["name"], student_count=row["student_count"])

    def create_class(self, name: str, students: list[str]) -> Class:
        name = (name or "").strip()
        if not name:
            raise ValueError("Class name is required.")
        student_names = _dedupe_students(students)
        if not student_names:
            raise ValueError("Add at least one student.")

        with self.db.transaction():
            try:
                cur = self.db.execute("INSERT INTO classes (name) VALUES (?)", (name,))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'Class "{name}" already exists.') from exc
            class_id = int(cur.lastrowid)
            self.db.conn.executemany(
                "INSERT INTO students (class_id, name) VALUES (?, ?)",
                [(class_id, s) for s in student_names],
            )
        return Class(id=class_id, name=name, student_count=len(student_names))

    def rename_class(self, class_id: int, new_name: str) -> None:
        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("Class name is required.")
        with self.db.transaction():
            try:
                self.db.execute(
                    "UPDATE classes SET name = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_name, class_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'Class "{new_name}" already exists.') from exc

    def delete_class(self, class_id: int) -> None:
        with self.db.transaction():
            self.db.execute("DELETE FROM classes WHERE id = ?", (class_id,))

    # ------------------------------------------------------------ students

    def list_students(self, class_id: int) -> list[Student]:
        rows = self.db.execute(
            """
            SELECT id, class_id, name, picks, correct, incorrect, volunteers, skips
            FROM students WHERE class_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (class_id,),
        ).fetchall()
        return [
            Student(
                id=r["id"],
                class_id=r["class_id"],
                name=r["name"],
                picks=r["picks"],
                correct=r["correct"],
                incorrect=r["incorrect"],
                volunteers=r["volunteers"],
                skips=r["skips"],
            )
            for r in rows
        ]

    def add_student(self, class_id: int, name: str) -> None:
        name = (name or "").strip()
        if not name:
            raise ValueError("Student name is required.")
        with self.db.transaction():
            try:
                self.db.execute(
                    "INSERT INTO students (class_id, name) VALUES (?, ?)", (class_id, name)
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'"{name}" is already in this class.') from exc

    def delete_student(self, student_id: int) -> None:
        with self.db.transaction():
            self.db.execute("DELETE FROM students WHERE id = ?", (student_id,))

    def remove_student(self, class_id: int, name: str) -> None:
        with self.db.transaction():
            self.db.execute(
                "DELETE FROM students WHERE class_id = ? AND name = ?", (class_id, name)
            )

    def rename_student(self, class_id: int, current_name: str, new_name: str) -> None:
        new_name = (new_name or "").strip()
        if not new_name:
            raise ValueError("Student name is required.")
        if new_name == current_name:
            return
        with self.db.transaction():
            try:
                cur = self.db.execute(
                    "UPDATE students SET name = ? WHERE class_id = ? AND name = ?",
                    (new_name, class_id, current_name),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f'"{new_name}" is already in this class.') from exc
            if cur.rowcount == 0:
                raise ValueError(f'"{current_name}" is not in this class.')

    # ------------------------------------------------------------- counters

    def apply_event(
        self, class_id: int, student_name: str, field: CounterField, delta: int = 1
    ) -> None:
        if field not in COUNTER_FIELDS:
            raise ValueError(f"Unknown counter field: {field}")
        with self.db.transaction():
            cur = self.db.execute(
                f"UPDATE students SET {field} = {field} + ? WHERE class_id = ? AND name = ?",
                (delta, class_id, student_name),
            )
            if cur.rowcount == 0:
                log.warning("apply_event: student %r not found", student_name)

    def set_stats(self, class_id: int, name: str, stats: dict) -> None:
        values = self._normalize_counters(stats)
        with self.db.transaction():
            self.db.execute(
                """
                INSERT INTO students
                    (class_id, name, picks, correct, incorrect, volunteers, skips)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(class_id, name) DO UPDATE SET
                    picks = excluded.picks,
                    correct = excluded.correct,
                    incorrect = excluded.incorrect,
                    volunteers = excluded.volunteers,
                    skips = excluded.skips
                """,
                (
                    class_id,
                    name,
                    values["picks"],
                    values["correct"],
                    values["incorrect"],
                    values["volunteers"],
                    values["skips"],
                ),
            )

    def reset_class_stats(self, class_id: int) -> None:
        with self.db.transaction():
            self.db.execute(
                """
                UPDATE students
                SET picks = 0, correct = 0, incorrect = 0, volunteers = 0, skips = 0
                WHERE class_id = ?
                """,
                (class_id,),
            )

    # ---------------------------------------------------------- bulk import

    def replace_all(self, classes: dict) -> tuple[int, int]:
        """Delete every class and recreate from the web-shaped dict."""
        class_count = 0
        student_count = 0
        with self.db.transaction():
            self.db.execute("DELETE FROM classes")
            for class_name, payload in classes.items():
                students = payload.get("students", {}) if isinstance(payload, dict) else {}
                cur = self.db.execute("INSERT INTO classes (name) VALUES (?)", (class_name,))
                class_id = int(cur.lastrowid)
                class_count += 1
                for student_name, stats in students.items():
                    values = self._normalize_counters(stats)
                    self.db.execute(
                        """
                        INSERT INTO students
                            (class_id, name, picks, correct, incorrect, volunteers, skips)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            class_id,
                            student_name,
                            values["picks"],
                            values["correct"],
                            values["incorrect"],
                            values["volunteers"],
                            values["skips"],
                        ),
                    )
                    student_count += 1
        return class_count, student_count

    def merge_all(self, classes: dict) -> tuple[int, int]:
        """Upsert: create missing classes/students, overwrite student counters."""
        class_count = 0
        student_count = 0
        with self.db.transaction():
            for class_name, payload in classes.items():
                students = payload.get("students", {}) if isinstance(payload, dict) else {}
                existing = self.db.execute(
                    "SELECT id FROM classes WHERE name = ?", (class_name,)
                ).fetchone()
                class_count += 1
                if existing is None:
                    cur = self.db.execute("INSERT INTO classes (name) VALUES (?)", (class_name,))
                    class_id = int(cur.lastrowid)
                else:
                    class_id = int(existing["id"])
                for student_name, stats in students.items():
                    values = self._normalize_counters(stats)
                    self.db.execute(
                        """
                        INSERT INTO students
                            (class_id, name, picks, correct, incorrect, volunteers, skips)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(class_id, name) DO UPDATE SET
                            picks = excluded.picks,
                            correct = excluded.correct,
                            incorrect = excluded.incorrect,
                            volunteers = excluded.volunteers,
                            skips = excluded.skips
                        """,
                        (
                            class_id,
                            student_name,
                            values["picks"],
                            values["correct"],
                            values["incorrect"],
                            values["volunteers"],
                            values["skips"],
                        ),
                    )
                    student_count += 1
        return class_count, student_count

    # ------------------------------------------------------------- settings

    def get_settings(self) -> Settings:
        rows = self.db.execute("SELECT key, value FROM settings").fetchall()
        stored: dict[str, object] = {}
        for row in rows:
            try:
                stored[row["key"]] = json.loads(row["value"])
            except (ValueError, TypeError):
                log.warning("Ignoring unreadable setting %r", row["key"])
        defaults = default_settings()
        valid = {f for f in Settings.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {}
        for field in valid:
            if field in stored:
                kwargs[field] = stored[field]
            else:
                kwargs[field] = getattr(defaults, field)
        return Settings(**kwargs)

    def save_settings(self, settings: Settings) -> None:
        with self.db.transaction():
            for field in Settings.__dataclass_fields__:  # type: ignore[attr-defined]
                self.db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (field, json.dumps(getattr(settings, field))),
                )

    # -------------------------------------------------------------- sessions

    def get_class_session(self, class_id: int) -> dict | None:
        """Return the persisted session payload for a class, or ``None``."""
        row = self.db.execute(
            "SELECT data FROM class_sessions WHERE class_id = ?", (class_id,)
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["data"])
        except (ValueError, TypeError):
            log.warning("Ignoring unreadable session for class %s", class_id)
            return None
        return payload if isinstance(payload, dict) else None

    def save_class_session(self, class_id: int, payload: dict) -> None:
        with self.db.transaction():
            self.db.execute(
                """
                INSERT INTO class_sessions (class_id, data, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(class_id) DO UPDATE SET
                    data = excluded.data,
                    updated_at = datetime('now')
                """,
                (class_id, json.dumps(payload)),
            )

    def delete_class_session(self, class_id: int) -> None:
        with self.db.transaction():
            self.db.execute("DELETE FROM class_sessions WHERE class_id = ?", (class_id,))

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _normalize_counters(stats: object) -> dict[str, int]:
        """Coerce arbitrary import data into the five non-negative integers."""
        result = {f: 0 for f in COUNTER_FIELDS}
        if stats is None:
            return result
        for field in COUNTER_FIELDS:
            if isinstance(stats, dict):
                raw = stats.get(field, 0)
            else:
                raw = getattr(stats, field, 0)
            try:
                value = int(raw)
            except (TypeError, ValueError):
                value = 0
            result[field] = max(0, value)
        return result
