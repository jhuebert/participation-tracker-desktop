"""Per-class runtime session state (persisted per class in SQLite).

Mirrors the web v2 ``participationSession`` store: attendance, per-session skip
usage, the last-picked student, and per-session counters. Lifetime counters live
in the ``students`` table; the values here exist so a class period survives an
app restart and so the picker can show *this session's* tallies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import COUNTER_FIELDS


def _empty_stats() -> dict[str, int]:
    return {f: 0 for f in COUNTER_FIELDS}


def _blank_stats(names) -> dict[str, dict[str, int]]:
    return {name: _empty_stats() for name in names}


@dataclass
class Session:
    class_id: int | None = None
    present: set[str] = field(default_factory=set)
    session_skips: dict[str, int] = field(default_factory=dict)
    session_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    current_student: str | None = None
    last_picked: str | None = None

    # ---------------------------------------------------------------- loading
    def load_class(self, klass, students) -> None:
        """Fresh session for a class: everyone present, counters reset."""
        self.class_id = getattr(klass, "id", klass if isinstance(klass, int) else None)
        names = [s.name if hasattr(s, "name") else str(s) for s in students]
        self.present = set(names)
        self.session_skips = {}
        self.session_stats = _blank_stats(names)
        self.current_student = None
        self.last_picked = None

    def load_payload(self, payload: dict | None, names) -> None:
        """Hydrate from persisted data, pruning students no longer enrolled."""
        enrolled = list(names)
        enrolled_set = set(enrolled)
        if not payload:
            self.present = set(enrolled)
            self.session_skips = {}
            self.session_stats = _blank_stats(enrolled)
            self.last_picked = None
        else:
            present = payload.get("present")
            if isinstance(present, list):
                self.present = {str(n) for n in present if str(n) in enrolled_set}
            else:
                self.present = set(enrolled)

            skips = payload.get("session_skips")
            self.session_skips = {}
            if isinstance(skips, dict):
                for name, count in skips.items():
                    if str(name) in enrolled_set:
                        try:
                            self.session_skips[str(name)] = max(0, int(count))
                        except (TypeError, ValueError):
                            continue

            raw_stats = payload.get("session_stats")
            self.session_stats = _blank_stats(enrolled)
            if isinstance(raw_stats, dict):
                for name, stats in raw_stats.items():
                    if str(name) not in enrolled_set or not isinstance(stats, dict):
                        continue
                    merged = _empty_stats()
                    for key in COUNTER_FIELDS:
                        try:
                            merged[key] = max(0, int(stats.get(key, 0)))
                        except (TypeError, ValueError):
                            merged[key] = 0
                    self.session_stats[str(name)] = merged

            last = payload.get("last_picked")
            self.last_picked = str(last) if isinstance(last, str) and last in enrolled_set else None

        self.current_student = None
        # Ensure every enrolled student has a counters bucket. Roster additions
        # are marked present by the roster-edit flow, not here.
        for name in enrolled:
            self.session_stats.setdefault(name, _empty_stats())

    def to_payload(self) -> dict:
        return {
            "present": sorted(self.present, key=str.casefold),
            "session_skips": {k: v for k, v in self.session_skips.items() if v},
            "session_stats": {k: dict(v) for k, v in self.session_stats.items() if any(v.values())},
            "last_picked": self.last_picked,
        }

    # ------------------------------------------------------------- mutations
    def reset_for_new_session(self, names) -> None:
        """Start a new period: everyone present, skips/stats/last-picked cleared."""
        self.present = set(names)
        self.session_skips = {}
        self.session_stats = _blank_stats(names)
        self.current_student = None
        self.last_picked = None

    def reset_skips(self) -> None:
        self.session_skips = {}

    def toggle_attendance(self, name: str, present: bool) -> None:
        if present:
            self.present.add(name)
        else:
            self.present.discard(name)

    def select_all(self, names) -> None:
        self.present = set(names)

    def deselect_all(self) -> None:
        self.present.clear()

    def can_skip(self, name: str, skip_limit: int) -> bool:
        return skip_limit <= 0 or self.session_skips.get(name, 0) < skip_limit

    def record_skip(self, name: str) -> None:
        self.session_skips[name] = self.session_skips.get(name, 0) + 1

    def record_event(self, name: str, field: str, delta: int = 1) -> None:
        stats = self.session_stats.setdefault(name, _empty_stats())
        stats[field] = max(0, stats.get(field, 0) + delta)

    def stats_for(self, name: str) -> dict[str, int]:
        return self.session_stats.get(name, _empty_stats())

    # ----------------------------------------------------------- roster edits
    def add_student(self, name: str) -> None:
        self.session_stats.setdefault(name, _empty_stats())
        self.present.add(name)

    def rename_student(self, old_name: str, new_name: str) -> None:
        if old_name == new_name:
            return
        if old_name in self.present:
            self.present.discard(old_name)
            self.present.add(new_name)
        if old_name in self.session_skips:
            self.session_skips[new_name] = self.session_skips.pop(old_name)
        if old_name in self.session_stats:
            self.session_stats[new_name] = self.session_stats.pop(old_name)
        if self.last_picked == old_name:
            self.last_picked = new_name
        if self.current_student == old_name:
            self.current_student = new_name

    def remove_student(self, name: str) -> None:
        self.present.discard(name)
        self.session_skips.pop(name, None)
        self.session_stats.pop(name, None)
        if self.last_picked == name:
            self.last_picked = None
        if self.current_student == name:
            self.current_student = None

    def clear_current(self) -> None:
        self.current_student = None
