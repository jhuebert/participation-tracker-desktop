"""Plain dataclasses mirroring the web app's data shape."""

from __future__ import annotations

from dataclasses import dataclass

# The five event counters, in the web app's export order.
COUNTER_FIELDS = ("picks", "correct", "incorrect", "volunteers", "skips")


@dataclass
class Student:
    id: int
    class_id: int
    name: str
    picks: int = 0
    correct: int = 0
    incorrect: int = 0
    volunteers: int = 0
    skips: int = 0

    def counters(self) -> dict[str, int]:
        return {f: getattr(self, f) for f in COUNTER_FIELDS}


@dataclass
class Class:
    id: int
    name: str
    student_count: int = 0


@dataclass
class Settings:
    skip_limit: int = 3
    weighted_enabled: bool = True

    weight_volunteer_amt: int = 30
    weight_volunteer_dir: str = "decrease"
    weight_correct_amt: int = 15
    weight_correct_dir: str = "decrease"
    weight_incorrect_amt: int = 10
    weight_incorrect_dir: str = "increase"
    weight_skip_amt: int = 20
    weight_skip_dir: str = "increase"

    scoring_correct_points: float = 2.0
    scoring_correct_effect: str = "add"
    scoring_volunteer_points: float = 1.0
    scoring_volunteer_effect: str = "add"
    scoring_incorrect_points: float = 1.0
    scoring_incorrect_effect: str = "subtract"
    scoring_skip_points: float = 1.0
    scoring_skip_effect: str = "subtract"

    overlay_enabled: bool = True

    chime_enabled: bool = True


def default_settings() -> Settings:
    return Settings()


__all__ = ["Student", "Class", "Settings", "default_settings", "COUNTER_FIELDS"]
