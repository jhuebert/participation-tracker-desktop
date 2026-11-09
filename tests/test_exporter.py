import csv, io, json
from participation_tracker.models import Settings, Student
from participation_tracker.services.exporter import to_backup_json, to_class_csv
from participation_tracker.services.importer import (
    extract_backup_settings,
    parse_backup_json,
    parse_class_csv,
)

def test_json_round_trip():
    classes = {"Math": {"students": {"Comma, Name": {"picks": 2, "correct": 1}}}}
    parsed = parse_backup_json(to_backup_json(classes))
    assert parsed["Math"]["students"]["Comma, Name"]["picks"] == 2


def test_backup_includes_settings_when_provided():
    settings = Settings(skip_limit=7, weighted_enabled=False, scoring_correct_points=3)
    text = to_backup_json({"Math": {"students": {"A": {"picks": 1}}}}, settings)
    obj = json.loads(text)
    assert obj["settings"]["skipLimit"] == 7
    assert obj["settings"]["weights"]["enabled"] is False
    parsed = extract_backup_settings(text)
    assert parsed["skip_limit"] == 7
    assert parsed["weighted_enabled"] is False
    assert parsed["scoring_correct_points"] == 3.0


def test_backup_without_settings_stays_legacy_shape():
    text = to_backup_json({"Math": {"students": {"A": {"picks": 1}}}})
    assert "settings" not in json.loads(text)
    assert extract_backup_settings(text) is None

def test_csv_web_header_and_quoting():
    text = to_class_csv("Math", [Student(1,1,'Doe, Jane',2,1,0,0,0)], Settings())
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["Rank", "Name", "Picks", "Volunteers", "Skips", "Correct", "Incorrect", "Total Participation Points", "Leaderboard Score"]
    assert rows[1][1] == "Doe, Jane"
    assert rows[1][7:] == ["2", "1.00"]
    assert parse_class_csv(text)[0][0] == "Doe, Jane"


def test_csv_ranking_and_scores_use_new_formula():
    students = [
        Student(1, 1, "Correct responses", picks=10, correct=10),
        Student(2, 1, "Volunteers", picks=10, correct=1, volunteers=3),
    ]
    rows = list(csv.reader(io.StringIO(to_class_csv("Math", students, Settings()))))
    assert [row[1] for row in rows[1:]] == ["Volunteers", "Correct responses"]
    assert [row[8] for row in rows[1:]] == ["3.20", "2.00"]
