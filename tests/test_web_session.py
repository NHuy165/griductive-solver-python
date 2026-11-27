"""Kiểm thử ``GameSession`` — cầu nối giữa engine, agent và giao diện."""

from __future__ import annotations

from src.game.core.core_types.level_solve_result import LevelSolveStatus
from src.web.app import LEVELS_BY_ID
from src.web.session import GameSession
from tests.helpers import (
    MAPS_DIR,
    build_full_formula,
    build_initial_formula,
    load_level,
)


def make_session() -> GameSession:
    return GameSession(
        MAPS_DIR / "level_01.json",
        LEVELS_BY_ID["level_01.json"],
    )


def test_initial_state() -> None:
    session = make_session()
    state = session.state()

    assert state["level"]["id"] == "level_01.json"
    assert state["map_size"] == 9
    assert state["flipped"] == [5]
    assert state["initial_flipped"] == [5]
    assert state["remaining"] == 8
    assert state["solved"] is False
    assert state["kb_clauses"] == session.initial_clauses
    assert state["stats"]["primary"] == 9
    assert state["stats"]["auxiliary"] == 0
    assert state["stats"]["initial_revealed"] == 1
    assert state["trace"] == []
    assert state["last_auto"] is None
    assert len(state["revealed_clues"]) == 1
    assert state["revealed_clues"][0]["id"] == "CL-5"


def test_state_hides_face_down_information() -> None:
    session = make_session()
    state = session.state()

    for person in state["people"]:
        if person["index"] in state["flipped"]:
            assert person["revealed"] is True
            assert person["status"] in {"CRIMINAL", "INNOCENT"}
            assert person["clue"]["id"] == f"CL-{person['index']}"
        else:
            assert person["revealed"] is False
            assert "status" not in person
            assert "clue" not in person


def test_coordinates_and_level_size() -> None:
    session = make_session()

    assert session.level_size() == 3
    assert session._coord(1) == "A1"
    assert session._coord(3) == "C1"
    assert session._coord(4) == "A2"
    assert session._coord(5) == "B2"
    assert session._coord(8) == "B3"
    assert session._coord(9) == "C3"


def test_query_strings() -> None:
    session = make_session()

    assert session._query(1, "CRIMINAL") == "KB ∧ ¬C_1 → UNSAT"
    assert session._query(1, "INNOCENT") == "KB ∧ C_1 → UNSAT"


def test_submit_verdict_rejects_invalid_index_and_flipped_card() -> None:
    session = make_session()
    before = session.state()

    assert session.submit_verdict(0, "CRIMINAL")["result"] == "ERROR"
    assert session.submit_verdict(10, "CRIMINAL")["result"] == "ERROR"
    assert session.submit_verdict(5, "CRIMINAL")["result"] == "ERROR"
    assert session.state()["flipped"] == before["flipped"]
    assert session.state()["trace"] == []


def test_submit_verdict_not_provable_keeps_state() -> None:
    session = make_session()
    before = session.state()

    payload = session.submit_verdict(1, "CRIMINAL")

    assert payload["result"] == "NOT_PROVABLE"
    assert payload["revealed_index"] is None
    assert payload["state"]["flipped"] == before["flipped"]
    assert payload["state"]["trace"] == []


def test_submit_verdict_contradicted_keeps_state() -> None:
    session = make_session()
    before = session.state()

    payload = session.submit_verdict(8, "INNOCENT")

    assert payload["result"] == "CONTRADICTED"
    assert payload["revealed_index"] is None
    assert payload["state"]["flipped"] == before["flipped"]
    assert payload["state"]["trace"] == []


def test_submit_verdict_reports_broken_knowledge_base() -> None:
    session = make_session()
    session.formula = [[1], [-1]]

    payload = session.submit_verdict(1, "CRIMINAL")

    assert payload["result"] == "ERROR"
    assert "mâu thuẫn" in payload["message"]
    assert payload["revealed_index"] is None
    assert payload["state"]["flipped"] == [5]


def test_submit_verdict_correct_updates_formula_and_trace() -> None:
    session = make_session()
    level, _ = load_level("level_01.json")
    initial_formula_length = len(session.formula)

    payload = session.submit_verdict(8, "CRIMINAL")

    assert payload["result"] == "CORRECT"
    assert payload["revealed_index"] == 8
    assert "Chính xác!" in payload["message"]
    assert "Heidi" in payload["message"]
    assert "TỘI PHẠM" in payload["message"]

    state = payload["state"]
    assert state["flipped"] == [5, 8]
    assert state["remaining"] == 7
    assert session.assignment[8] is True
    assert session.step_count == 1
    assert len(session.formula) == (
        initial_formula_length
        + 1
        + len(level.get_person(8).get_clue().to_cnf())
    )
    assert state["stats"]["kb_clauses"] == len(session.formula)
    assert len(state["trace"]) == 1
    trace = state["trace"][0]
    assert trace["step"] == 1
    assert trace["kind"] == "manual"
    assert trace["active_clue_ids"] == ["CL-5"]
    assert trace["query"] == "KB ∧ ¬C_8 → UNSAT"
    assert trace["verdict"] == "CRIMINAL"
    assert trace["index"] == 8
    assert trace["coord"] == "B3"
    assert trace["name"] == "Heidi"
    assert trace["new_clue_id"] == "CL-8"


def test_reset_restores_initial_state() -> None:
    session = make_session()
    session.submit_verdict(8, "CRIMINAL")

    session.reset()
    state = session.state()

    assert state["flipped"] == [5]
    assert state["initial_flipped"] == [5]
    assert state["remaining"] == 8
    assert state["solved"] is False
    assert state["trace"] == []
    assert state["last_auto"] is None
    assert session.assignment == {5: True}
    assert session.step_count == 0
    assert len(session.formula) == session.initial_clauses


def test_hint_returns_forced_person_without_changing_state() -> None:
    session = make_session()
    before = session.state()

    payload = session.hint()

    assert payload["hint"] is not None
    hint = payload["hint"]
    assert hint["index"] == 8
    assert hint["coord"] == "B3"
    assert hint["name"] == "Heidi"
    assert hint["occupation"] == "Farmer"
    assert hint["icon"] == "mdi--sprout.svg"
    assert hint["clue_ids"] == ["CL-5"]
    assert "Gợi ý" in payload["message"]
    assert payload["state"]["flipped"] == before["flipped"]
    assert payload["state"]["trace"] == []


def test_hint_returns_none_when_level_is_solved() -> None:
    session = make_session()
    session.auto_solve()

    payload = session.hint()

    assert payload["hint"] is None
    assert "không còn" in payload["message"]
    assert payload["state"]["solved"] is True


def test_auto_message_for_stuck_and_inconsistent_status() -> None:
    session = make_session()

    stuck = session._auto_message(LevelSolveStatus.STUCK, {})
    inconsistent = session._auto_message(
        LevelSolveStatus.INCONSISTENT, {}
    )

    assert "không còn" in stuck
    assert "mâu thuẫn" in inconsistent


def test_auto_solve_updates_state_and_returns_summary() -> None:
    session = make_session()

    payload = session.auto_solve()
    summary = payload["summary"]
    state = payload["state"]

    assert summary["status"] == "SUCCESS"
    assert summary["waves"] == 7
    assert summary["sat_calls"] > 0
    assert summary["decisions"] >= 0
    assert summary["propagations"] >= 0
    assert summary["backtracks"] >= 0
    assert summary["time_ms"] >= 0.0
    assert summary["final_flipped"] == 9
    assert state["solved"] is True
    assert state["remaining"] == 0
    assert state["flipped"] == list(range(1, 10))
    assert state["last_auto"] == summary
    assert session.last_auto == summary
    assert len(state["trace"]) == 8
    assert all(entry["kind"] == "auto" for entry in state["trace"])

    steps = payload["steps"]
    assert len(steps) == 7
    for step_index, step in enumerate(steps, start=1):
        assert step["wave"] == step_index
        assert step["active_clue_ids"]
        assert all(
            clue_id.startswith("CL-") for clue_id in step["active_clue_ids"]
        )
        assert len(step["verdicts"]) == len(step["new_people"])
        assert len(step["verdicts"]) == len(step["new_clue_ids"])
        assert step["sat_calls"] >= 1
        assert set(step["events"]) == {
            "PROPAGATION",
            "DECISION",
            "BACKTRACK",
        }

    first = steps[0]
    assert first["new_clue_ids"] == ["CL-8"]
    assert first["verdicts"][0]["index"] == 8
    assert first["verdicts"][0]["status"] == "CRIMINAL"
    assert first["verdicts"][0]["coord"] == "B3"
    assert first["new_people"][0]["clue"]["id"] == "CL-8"
    assert first["kb_clauses_after"] > session.initial_clauses
    assert steps[-1]["kb_clauses_after"] == len(session.formula)


def test_auto_solve_twice_is_idempotent() -> None:
    session = make_session()
    first = session.auto_solve()
    second = session.auto_solve()

    assert first["summary"]["status"] == "SUCCESS"
    assert second["summary"]["status"] == "SUCCESS"
    assert second["summary"]["waves"] == 0
    assert second["summary"]["sat_calls"] == 0
    assert second["summary"]["final_flipped"] == 9
    assert second["state"]["solved"] is True


def test_clues_referencing_uses_only_revealed_clues() -> None:
    session = make_session()

    assert session._clues_referencing(8) == ["CL-5"]
    assert session._clues_referencing(5) == ["CL-5"]
    assert session._clues_referencing(1) == []


def test_full_and_initial_clause_counts() -> None:
    session = make_session()
    level, _ = load_level("level_01.json")
    state = session.state()

    assert session.full_clauses == len(build_full_formula(level))
    assert session.initial_clauses == len(build_initial_formula(level))
    assert state["stats"]["full_clauses"] == session.full_clauses
    assert state["stats"]["initial_clauses"] == session.initial_clauses


def test_person_and_clue_payloads() -> None:
    session = make_session()

    hidden = session._person_payload(1)
    assert hidden["revealed"] is False
    assert "status" not in hidden
    assert "clue" not in hidden

    revealed = session._person_payload(5)
    assert revealed["revealed"] is True
    assert revealed["status"] == "CRIMINAL"
    assert revealed["clue"]["id"] == "CL-5"

    clue = session._clue_payload(5)
    assert clue["id"] == "CL-5"
    assert clue["owner"] == 5
    assert clue["owner_name"] == "Eve"
    assert clue["owner_coord"] == "B2"
    assert clue["type"] == "EXACTLY"
    assert clue["region"] == [5, 8]
    assert "Eve" in clue["text"]
    assert "Heidi" in clue["text"]


def test_active_clue_ids() -> None:
    session = make_session()

    assert session._active_clue_ids() == ["CL-5"]
