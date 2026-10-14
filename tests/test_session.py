from participation_tracker.services.session import Session


def test_session_resets_ephemeral_state_and_enforces_skip_limit():
    session = Session()
    session.load_class(type("K", (), {"id": 7})(), ["A", "B"])
    assert session.present == {"A", "B"}
    assert session.can_skip("A", 2)
    session.record_skip("A")
    assert session.can_skip("A", 2)
    session.record_skip("A")
    assert not session.can_skip("A", 2)
    session.current_student = "B"
    session.last_picked = "B"
    session.load_class(type("K", (), {"id": 7})(), ["A", "B"])
    assert session.current_student is None and session.last_picked is None
    assert session.session_skips == {}


def test_unlimited_skip_limit_and_attendance():
    session = Session()
    session.load_class(3, ["A", "B"])
    session.deselect_all()
    session.toggle_attendance("A", True)
    assert session.present == {"A"}
    assert session.can_skip("A", 0)


def test_load_payload_prunes_and_hydrates():
    session = Session()
    payload = {
        "present": ["A", "Ghost"],
        "session_skips": {"A": 2, "Ghost": 9},
        "session_stats": {"A": {"picks": 3, "correct": 1}, "Ghost": {"picks": 5}},
        "last_picked": "Ghost",
    }
    session.load_payload(payload, ["A", "B"])
    assert session.present == {"A"}  # Ghost pruned, B not auto-present
    assert session.session_skips == {"A": 2}
    assert session.stats_for("A")["picks"] == 3
    assert session.stats_for("A")["correct"] == 1
    assert "Ghost" not in session.session_stats
    assert session.last_picked is None  # last-picked student no longer enrolled
    assert session.stats_for("B") == {"picks": 0, "correct": 0, "incorrect": 0, "volunteers": 0, "skips": 0}


def test_load_payload_defaults_everyone_present():
    session = Session()
    session.load_payload(None, ["A", "B"])
    assert session.present == {"A", "B"}
    session.load_payload({}, ["A", "B"])
    assert session.present == {"A", "B"}


def test_payload_round_trip():
    session = Session()
    session.class_id = 1
    session.load_class(1, ["A", "B"])
    session.toggle_attendance("B", False)
    session.record_event("A", "picks")
    session.record_event("A", "correct")
    session.record_skip("A")
    session.last_picked = "A"
    payload = session.to_payload()

    restored = Session()
    restored.load_payload(payload, ["A", "B"])
    assert restored.present == {"A"}
    assert restored.session_skips == {"A": 1}
    assert restored.stats_for("A")["picks"] == 1
    assert restored.stats_for("A")["correct"] == 1
    assert restored.last_picked == "A"


def test_roster_edits_follow_into_session():
    session = Session()
    session.load_class(1, ["A", "B"])
    session.record_event("A", "picks")
    session.record_skip("A")
    session.last_picked = "A"

    session.rename_student("A", "A2")
    assert "A2" in session.present and "A" not in session.present
    assert session.session_skips == {"A2": 1}
    assert session.stats_for("A2")["picks"] == 1
    assert session.last_picked == "A2"

    session.add_student("C")
    assert "C" in session.present
    assert session.stats_for("C")["picks"] == 0

    session.remove_student("A2")
    assert "A2" not in session.present
    assert "A2" not in session.session_skips
    assert session.last_picked is None


def test_reset_for_new_session_and_skips():
    session = Session()
    session.load_class(1, ["A", "B"])
    session.toggle_attendance("B", False)
    session.record_skip("A")
    session.record_event("A", "correct")
    session.last_picked = "A"

    session.reset_skips()
    assert session.session_skips == {}
    assert session.last_picked == "A"  # skips-only reset keeps last-picked

    session.reset_for_new_session(["A", "B"])
    assert session.present == {"A", "B"}
    assert session.session_skips == {}
    assert session.stats_for("A")["correct"] == 0
    assert session.last_picked is None
