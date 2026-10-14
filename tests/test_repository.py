from participation_tracker.db.database import CURRENT_VERSION, MIGRATIONS, Database
from participation_tracker.models import Settings

def test_crud_and_dedupe(repo):
    klass = repo.create_class("  Period 1 ", [" Ada ", "ada", "", "Bo"])
    assert klass.name == "Period 1" and klass.student_count == 2
    assert [s.name for s in repo.list_students(klass.id)] == ["Ada", "Bo"]
    repo.apply_event(klass.id, "Ada", "picks")
    repo.apply_event(klass.id, "Ada", "correct", 2)
    assert repo.list_students(klass.id)[0].picks == 1
    repo.reset_class_stats(klass.id)
    assert repo.list_students(klass.id)[0].correct == 0
    repo.delete_class(klass.id)
    assert repo.list_classes() == []

def test_replace_merge_settings(repo):
    source = {"Math": {"students": {"Alex": {"picks": 2, "correct": 1}}}}
    assert repo.replace_all(source) == (1, 1)
    klass = repo.get_class_by_name("Math")
    repo.set_stats(klass.id, "Alex", {"picks": 5})
    repo.merge_all(source)
    assert repo.list_students(klass.id)[0].picks == 2
    settings = Settings(skip_limit=7, overlay_enabled=False)
    repo.save_settings(settings)
    assert repo.get_settings() == settings


def test_rename_and_remove_student(repo):
    klass = repo.create_class("Math", ["Ada", "Bo"])
    repo.apply_event(klass.id, "Ada", "picks", 3)
    repo.rename_student(klass.id, "Ada", "Ada Lovelace")
    names = [s.name for s in repo.list_students(klass.id)]
    assert names == ["Ada Lovelace", "Bo"]
    assert next(s for s in repo.list_students(klass.id) if s.name == "Ada Lovelace").picks == 3

    import pytest
    with pytest.raises(ValueError):
        repo.rename_student(klass.id, "Bo", "Ada Lovelace")  # duplicate
    with pytest.raises(ValueError):
        repo.rename_student(klass.id, "Ghost", "New")
    with pytest.raises(ValueError):
        repo.rename_student(klass.id, "Bo", "  ")

    repo.remove_student(klass.id, "Bo")
    assert [s.name for s in repo.list_students(klass.id)] == ["Ada Lovelace"]


def test_class_session_round_trip(repo):
    klass = repo.create_class("Math", ["A", "B"])
    assert repo.get_class_session(klass.id) is None
    payload = {"present": ["A"], "session_skips": {"A": 1}, "last_picked": "A"}
    repo.save_class_session(klass.id, payload)
    assert repo.get_class_session(klass.id) == payload
    repo.save_class_session(klass.id, {"present": ["B"]})
    assert repo.get_class_session(klass.id) == {"present": ["B"]}
    repo.delete_class_session(klass.id)
    assert repo.get_class_session(klass.id) is None


def test_sessions_cascade_on_class_delete(repo):
    klass = repo.create_class("Math", ["A"])
    repo.save_class_session(klass.id, {"present": ["A"]})
    repo.delete_class(klass.id)
    assert repo.get_class_session(klass.id) is None


def test_migration_adds_session_table(tmp_path):
    import sqlite3
    db = Database(tmp_path / "old.db")
    db.initialize()
    assert CURRENT_VERSION == 2 and len(MIGRATIONS) == 1
    # Simulate an old v1 database: drop the table and reset the version.
    db.conn.execute("DROP TABLE class_sessions")
    db.conn.execute("UPDATE schema_version SET version = 1")
    db.close()

    reopened = Database(tmp_path / "old.db")
    reopened.initialize()
    version = reopened.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == CURRENT_VERSION
    row = reopened.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='class_sessions'"
    ).fetchone()
    assert row is not None
    reopened.close()
