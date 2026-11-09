import pytest

from participation_tracker.models import Settings, Student
from participation_tracker.services.scoring import leaderboard_score, participation_points

def test_default_score_and_rounding():
    stats = {"picks": 2, "correct": 1, "volunteers": 1, "incorrect": 1, "skips": 1}
    settings = Settings()
    assert participation_points(stats, settings) == 1.0
    assert leaderboard_score(stats, settings) == 0.0

def test_all_effect_combinations():
    settings = Settings(scoring_correct_effect="subtract", scoring_volunteer_effect="subtract", scoring_incorrect_effect="add", scoring_skip_effect="add")
    assert participation_points({"correct": 1, "volunteers": 2, "incorrect": 3, "skips": 4}, settings) == 3.0

def test_no_picks_and_float_rounding():
    assert leaderboard_score({"picks": 0}, Settings()) == 0
    settings = Settings(scoring_correct_points=0.333)
    assert participation_points({"correct": 1}, settings) == 0.33


@pytest.mark.parametrize("as_student", [False, True])
def test_score_uses_settings_and_only_divides_correct_by_picks(as_student):
    counters = {"picks": 4, "correct": 3, "volunteers": 2, "skips": 1, "incorrect": 2}
    stats = Student(1, 1, "Student", **counters) if as_student else counters
    settings = Settings(
        scoring_correct_points=3.5,
        scoring_volunteer_points=2.25,
        scoring_skip_points=0.75,
        scoring_incorrect_points=1.5,
    )
    assert leaderboard_score(stats, settings) == pytest.approx(3 * 3.5 / 4 + 2 * 2.25 - 0.75 - 2 * 1.5)


def test_score_respects_reversed_scoring_effects():
    settings = Settings(
        scoring_correct_effect="subtract", scoring_volunteer_effect="subtract",
        scoring_skip_effect="add", scoring_incorrect_effect="add",
    )
    stats = {"picks": 4, "correct": 3, "volunteers": 2, "skips": 1, "incorrect": 2}
    assert leaderboard_score(stats, settings) == -3 * 2 / 4 - 2 + 1 + 2


def test_score_does_not_round_contributions_before_dividing():
    settings = Settings(scoring_correct_points=0.333)
    assert leaderboard_score({"picks": 2, "correct": 1}, settings) == pytest.approx(0.1665)


def test_no_picks_preserves_zero_score_with_other_counters():
    assert leaderboard_score({"picks": 0, "correct": 1, "volunteers": 2, "skips": 1}, Settings()) == 0.0
