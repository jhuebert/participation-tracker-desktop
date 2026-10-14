"""Weighted and uniform student selection."""

from __future__ import annotations

import random
from collections.abc import Mapping, Set

from ..models import Settings, Student


def _value(student: Student | Mapping, key: str, default: int = 0):
    return student.get(key, default) if isinstance(student, Mapping) else getattr(student, key, default)


def _setting(settings: Settings | Mapping, key: str, default):
    return settings.get(key, default) if isinstance(settings, Mapping) else getattr(settings, key, default)


def _weight_for(student: Student | Mapping, settings: Settings | Mapping) -> int:
    weight = 100
    for field, amt_field, dir_field in (
        ("volunteers", "weight_volunteer_amt", "weight_volunteer_dir"),
        ("correct", "weight_correct_amt", "weight_correct_dir"),
        ("incorrect", "weight_incorrect_amt", "weight_incorrect_dir"),
        ("skips", "weight_skip_amt", "weight_skip_dir"),
    ):
        amount = _setting(settings, amt_field, 0)
        direction = _setting(settings, dir_field, "decrease")
        count = _value(student, field, 0)
        weight += (-1 if direction == "decrease" else 1) * amount * count
    return max(1, int(weight))


def _weighted_choice(names: list[str], students: Mapping[str, Student], settings: Settings, rng: random.Random) -> str:
    weights = [_weight_for(students[name], settings) for name in names]
    target = rng.random() * sum(weights)
    for name, weight in zip(names, weights):
        target -= weight
        if target < 0:
            return name
    return names[-1]


def pick_random(
    present: Set[str],
    students: dict[str, Student],
    settings: Settings,
    last_picked: str | None,
    rng: random.Random | None = None,
) -> str:
    """Return the chosen student name. Raises ValueError if nobody eligible."""
    rng = rng or random.Random()
    if not present:
        raise ValueError("no students present")
    names = sorted(n for n in present if n in students)
    if not names:
        raise ValueError("no students present")
    eligible = [n for n in names if n != last_picked]
    if not eligible:
        min_picks = min(_value(students[n], "picks", 0) for n in names)
        eligible = [n for n in names if _value(students[n], "picks", 0) == min_picks]
    if not _setting(settings, "weighted_enabled", True):
        return rng.choice(eligible)
    return _weighted_choice(eligible, students, settings, rng)
