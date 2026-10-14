"""Import web JSON backups and per-class CSV files."""

from __future__ import annotations

import csv
import io
import json

COUNTERS = ("picks", "correct", "incorrect", "volunteers", "skips")


class ImportError(ValueError):
    """User-facing import validation error."""


def _counter(raw) -> int:
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError, OverflowError):
        return 0


def parse_backup_json(text: str) -> dict[str, dict]:
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ImportError(f"Could not read backup JSON: {exc}") from exc
    if not isinstance(obj, dict) or obj.get("app") != "Participation Tracker":
        raise ImportError('This is not a Participation Tracker backup (expected app "Participation Tracker").')
    if not isinstance(obj.get("data"), dict):
        raise ImportError("Backup is missing its class data.")
    normalized: dict[str, dict] = {}
    for raw_class_name, payload in obj["data"].items():
        class_name = str(raw_class_name).strip()
        if not class_name or not isinstance(payload, dict):
            continue
        raw_students = payload.get("students", {})
        if not isinstance(raw_students, dict):
            continue
        students = {}
        for raw_name, raw_stats in raw_students.items():
            name = str(raw_name).strip()
            if not name:
                continue
            raw_stats = raw_stats if isinstance(raw_stats, dict) else {}
            students[name] = {field: _counter(raw_stats.get(field, 0)) for field in COUNTERS}
        normalized[class_name] = {"students": students}
    return normalized


def _number(value, cast):
    try:
        result = cast(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(result, float) and result != result:  # NaN
        return None
    return result


def extract_backup_settings(text: str) -> dict | None:
    """Read the optional ``settings`` extension block from a backup.

    Returns a partial mapping of ``Settings`` field names, or ``None`` when the
    backup carries no (readable) settings. Older web backups simply omit it.
    """
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    raw = obj.get("settings")
    if not isinstance(raw, dict):
        return None

    result: dict[str, object] = {}

    skip_limit = _number(raw.get("skipLimit"), lambda v: int(float(v)))
    if skip_limit is not None:
        result["skip_limit"] = max(0, skip_limit)

    scoring = raw.get("scoring")
    if isinstance(scoring, dict):
        for key in ("correct", "volunteer", "incorrect", "skip"):
            points = _number(scoring.get(f"{key}Points"), float)
            if points is not None:
                result[f"scoring_{key}_points"] = max(0.0, points)
            effect = scoring.get(f"{key}Effect")
            if effect in ("add", "subtract"):
                result[f"scoring_{key}_effect"] = effect

    weights = raw.get("weights")
    if isinstance(weights, dict):
        if isinstance(weights.get("enabled"), bool):
            result["weighted_enabled"] = weights["enabled"]
        for key in ("volunteer", "correct", "incorrect", "skip"):
            amt = _number(weights.get(f"{key}Amt"), lambda v: int(float(v)))
            if amt is not None:
                result[f"weight_{key}_amt"] = max(0, amt)
            direction = weights.get(f"{key}Dir")
            if direction in ("increase", "decrease"):
                result[f"weight_{key}_dir"] = direction

    if isinstance(raw.get("overlayEnabled"), bool):
        result["overlay_enabled"] = raw["overlayEnabled"]

    return result or None


def parse_class_csv(text: str) -> list[tuple[str, dict]]:
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        header = reader.fieldnames or []
        columns = {"picks": "Picks", "correct": "Correct", "incorrect": "Incorrect", "volunteers": "Volunteers", "skips": "Skips"}
        required = {"Name", *columns.values()}
        missing = sorted(required - set(header))
        if missing:
            raise ImportError("CSV is missing required column(s): " + ", ".join(missing))
        students: list[tuple[str, dict]] = []
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            stats = {field: _counter(row.get(column, 0)) for field, column in columns.items()}
            students.append((name, stats))
        return students
    except csv.Error as exc:
        raise ImportError(f"Could not read CSV: {exc}") from exc
