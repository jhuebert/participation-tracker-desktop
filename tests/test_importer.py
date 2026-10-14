from pathlib import Path
import pytest
from participation_tracker.services.importer import (
    ImportError,
    extract_backup_settings,
    parse_backup_json,
    parse_class_csv,
)
FIXTURES = Path(__file__).parent / "fixtures"

def test_parse_json_fixture():
    data = parse_backup_json((FIXTURES / "backup_sample.json").read_text())
    assert data["Period 1 - Math"]["students"]["Doe, Jane"]["picks"] == 2

def test_parse_csv_quotes_and_order():
    rows = parse_class_csv((FIXTURES / "Period_1_math_statistics.csv").read_text())
    assert rows[0][0] == "Doe, Jane"
    assert rows[1][0] == 'John "JJ" Smith'

def test_invalid_json_and_csv():
    with pytest.raises(ImportError): parse_backup_json('{"app":"bad","data":{}}')
    with pytest.raises(ImportError): parse_class_csv("Rank,Name\n1,A")

def test_missing_counters_default_and_negative_clamp():
    data = parse_backup_json('{"app":"Participation Tracker","data":{"X":{"students":{"Y":{"picks":-2}}}}}')
    assert data["X"]["students"]["Y"] == {"picks":0,"correct":0,"incorrect":0,"volunteers":0,"skips":0}


def test_extract_settings_absent_returns_none():
    assert extract_backup_settings('{"app":"Participation Tracker","data":{}}') is None
    assert extract_backup_settings('{"app":"Participation Tracker","data":{},"settings":{}}') is None
    assert extract_backup_settings("not json") is None


def test_extract_settings_maps_fields_and_ignores_invalid():
    text = '''{
      "app": "Participation Tracker",
      "data": {},
      "settings": {
        "skipLimit": 5,
        "scoring": {"correctPoints": 3, "correctEffect": "subtract", "skipEffect": "bogus"},
        "weights": {"enabled": false, "volunteerAmt": 40, "volunteerDir": "increase"},
        "overlayEnabled": false
      }
    }'''
    parsed = extract_backup_settings(text)
    assert parsed["skip_limit"] == 5
    assert parsed["scoring_correct_points"] == 3.0
    assert parsed["scoring_correct_effect"] == "subtract"
    assert "scoring_skip_effect" not in parsed  # invalid effect ignored
    assert parsed["weighted_enabled"] is False
    assert parsed["weight_volunteer_amt"] == 40
    assert parsed["weight_volunteer_dir"] == "increase"
    assert parsed["overlay_enabled"] is False
