from participation_tracker.models import Settings
from participation_tracker.services.scoring import leaderboard_score, participation_points

def test_default_score_and_rounding():
    stats = {"picks": 2, "correct": 1, "volunteers": 1, "incorrect": 1, "skips": 1}
    settings = Settings()
    assert participation_points(stats, settings) == 1.0
    assert leaderboard_score(stats, settings) == 0.5

def test_all_effect_combinations():
    settings = Settings(scoring_correct_effect="subtract", scoring_volunteer_effect="subtract", scoring_incorrect_effect="add", scoring_skip_effect="add")
    assert participation_points({"correct": 1, "volunteers": 2, "incorrect": 3, "skips": 4}, settings) == 3.0

def test_no_picks_and_float_rounding():
    assert leaderboard_score({"picks": 0}, Settings()) == 0
    settings = Settings(scoring_correct_points=0.333)
    assert participation_points({"correct": 1}, settings) == 0.33
