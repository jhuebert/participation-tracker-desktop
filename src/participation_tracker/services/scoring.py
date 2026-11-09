"""Participation point and leaderboard calculations."""

from __future__ import annotations


def _get(obj: object, key: str, default=0):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _contributions(stats: object, settings: object) -> tuple[float, float, float, float]:
    """Signed correct, volunteer, skip, and incorrect contributions from Settings."""
    def apply(effect: str, points: float, count: int) -> float:
        value = points * count
        return value if effect == "add" else -value

    return (
        apply(_get(settings, "scoring_correct_effect", "add"), _get(settings, "scoring_correct_points", 2.0), _get(stats, "correct", 0)),
        apply(_get(settings, "scoring_volunteer_effect", "add"), _get(settings, "scoring_volunteer_points", 1.0), _get(stats, "volunteers", 0)),
        apply(_get(settings, "scoring_skip_effect", "subtract"), _get(settings, "scoring_skip_points", 1.0), _get(stats, "skips", 0)),
        apply(_get(settings, "scoring_incorrect_effect", "subtract"), _get(settings, "scoring_incorrect_points", 1.0), _get(stats, "incorrect", 0)),
    )


def participation_points(stats: object, settings: object) -> float:
    return round(sum(_contributions(stats, settings)), 2)


def leaderboard_score(stats: object, settings: object) -> float:
    """Normalize only correct-response points by picks; add other terms directly."""
    picks = _get(stats, "picks", 0)
    if picks == 0:
        return 0.0
    correct, volunteer, skip, incorrect = _contributions(stats, settings)
    return correct / picks + volunteer + skip + incorrect
