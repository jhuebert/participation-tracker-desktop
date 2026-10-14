import random
import pytest
from participation_tracker.models import Settings, Student
from participation_tracker.services.picker import _weight_for, pick_random

def student(name, **kwargs):
    return Student(1, 1, name, **kwargs)

def test_excludes_last_and_fallback_fewest_picks():
    students = {"A": student("A", picks=8), "B": student("B", picks=2)}
    settings = Settings(weighted_enabled=False)
    assert pick_random({"A", "B"}, students, settings, "A", random.Random(1)) == "B"
    assert pick_random({"B"}, students, settings, "B", random.Random(1)) == "B"

def test_weight_clamps_to_one():
    assert _weight_for(student("A", volunteers=20), Settings()) == 1

def test_empty_present():
    with pytest.raises(ValueError, match="no students present"):
        pick_random(set(), {}, Settings(), None)

def test_weighted_choices_are_deterministic():
    students = {"A": student("A"), "B": student("B", incorrect=20)}
    settings = Settings(weight_incorrect_amt=10, weight_incorrect_dir="increase")
    assert pick_random(set(students), students, settings, None, random.Random(2)) == pick_random(set(students), students, settings, None, random.Random(2))


def test_weighted_and_uniform_use_different_draws():
    students = {"A": student("A"), "B": student("B", volunteers=100)}
    weighted = pick_random(set(students), students, Settings(), None, random.Random(0))
    uniform = pick_random(set(students), students, Settings(weighted_enabled=False), None, random.Random(0))
    assert weighted == "A"
    assert uniform == "B"
