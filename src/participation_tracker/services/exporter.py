"""Web-compatible JSON backup and CSV export."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path

from ..models import COUNTER_FIELDS
from .scoring import leaderboard_score, participation_points


def _stats_dict(stats: object) -> dict[str, int]:
    if isinstance(stats, dict):
        return {field: int(stats.get(field, 0) or 0) for field in COUNTER_FIELDS}
    return {field: int(getattr(stats, field, 0) or 0) for field in COUNTER_FIELDS}


def _setting(settings: object, field: str, default):
    if settings is None:
        return default
    if isinstance(settings, dict):
        return settings.get(field, default)
    return getattr(settings, field, default)


def settings_payload(settings: object) -> dict:
    """Serialize scoring/weight settings into a web-compatible extension shape."""
    return {
        "skipLimit": int(_setting(settings, "skip_limit", 3)),
        "scoring": {
            "correctPoints": float(_setting(settings, "scoring_correct_points", 2.0)),
            "correctEffect": _setting(settings, "scoring_correct_effect", "add"),
            "volunteerPoints": float(_setting(settings, "scoring_volunteer_points", 1.0)),
            "volunteerEffect": _setting(settings, "scoring_volunteer_effect", "add"),
            "incorrectPoints": float(_setting(settings, "scoring_incorrect_points", 1.0)),
            "incorrectEffect": _setting(settings, "scoring_incorrect_effect", "subtract"),
            "skipPoints": float(_setting(settings, "scoring_skip_points", 1.0)),
            "skipEffect": _setting(settings, "scoring_skip_effect", "subtract"),
        },
        "weights": {
            "enabled": bool(_setting(settings, "weighted_enabled", True)),
            "volunteerAmt": int(_setting(settings, "weight_volunteer_amt", 30)),
            "volunteerDir": _setting(settings, "weight_volunteer_dir", "decrease"),
            "correctAmt": int(_setting(settings, "weight_correct_amt", 15)),
            "correctDir": _setting(settings, "weight_correct_dir", "decrease"),
            "incorrectAmt": int(_setting(settings, "weight_incorrect_amt", 10)),
            "incorrectDir": _setting(settings, "weight_incorrect_dir", "increase"),
            "skipAmt": int(_setting(settings, "weight_skip_amt", 20)),
            "skipDir": _setting(settings, "weight_skip_dir", "increase"),
        },
        "overlayEnabled": bool(_setting(settings, "overlay_enabled", True)),
    }


def to_backup_json(classes: dict, settings: object | None = None) -> str:
    data: dict[str, dict] = {}
    for name, payload in classes.items():
        source_students = payload.get("students", {}) if isinstance(payload, dict) else {}
        data[name] = {"students": {n: _stats_dict(stats) for n, stats in source_students.items()}}
    now = datetime.now().astimezone()
    date = now.strftime("%#m/%#d/%Y, %#I:%M:%S %p") if __import__("os").name == "nt" else now.strftime("%-m/%-d/%Y, %-I:%M:%S %p")
    obj = {
        "app": "Participation Tracker",
        "date": date,
        "data": data,
    }
    if settings is not None:
        obj["settings"] = settings_payload(settings)
    return json.dumps(obj, indent=2, ensure_ascii=False)


def to_class_csv(klass_name: str, students, settings) -> str:
    """Create per-class CSV sorted by leaderboard score descending."""
    items = list(students.items()) if isinstance(students, dict) else [(s.name, s) for s in students]
    items.sort(key=lambda pair: leaderboard_score(pair[1], settings), reverse=True)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Rank", "Name", "Picks", "Volunteers", "Skips", "Correct", "Incorrect", "Total Participation Points", "Leaderboard Score"])
    for index, (name, stats) in enumerate(items, 1):
        values = _stats_dict(stats)
        score = leaderboard_score(stats, settings)
        points = participation_points(stats, settings)
        writer.writerow([
            index, name, values["picks"], values["volunteers"], values["skips"],
            values["correct"], values["incorrect"], f"{points:g}",
            f"{score:.2f}" if values["picks"] else "0",
        ])
    return output.getvalue()


def export_backup(path: str | Path, classes: dict, settings: object | None = None) -> None:
    Path(path).write_text(to_backup_json(classes, settings), encoding="utf-8")


def export_csv(path: str | Path, klass_name: str, students, settings) -> None:
    Path(path).write_text(to_class_csv(klass_name, students, settings), encoding="utf-8", newline="")
