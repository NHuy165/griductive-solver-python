"""Kiểm thử lớp web Flask ở mức HTTP.

Các kiểm thử dùng Flask test client, không mở cổng mạng thật. Chúng xác nhận
giao diện công khai không làm lộ trạng thái/manh mối của lá bài còn úp, đồng
thời kiểm tra đầy đủ các endpoint Load, Restart, Verdict, Hint, Auto Solve.
"""

from __future__ import annotations

import pytest

from src.web.app import create_app


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_renders(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"Griductive" in response.data


def test_api_levels_lists_all_levels(client) -> None:
    response = client.get("/api/levels")

    assert response.status_code == 200
    levels = response.get_json()["levels"]
    assert len(levels) == 30
    assert [level["number"] for level in levels] == list(range(1, 31))
    assert [level["size"] for level in levels] == [3] * 10 + [4] * 10 + [5] * 10
    assert levels[0]["id"] == "level_01.json"
    assert levels[0]["title"] == "Vườn chuối"
    assert levels[0]["difficulty"] == "Khởi động"
    assert levels[0]["extensions"] == []

    for level in levels:
        assert level["people_count"] == level["size"] ** 2
        assert level["initial_revealed"] >= 1
        assert isinstance(level["clue_types"], list)
        assert isinstance(level["caption"], str)


def test_api_state_returns_public_state(client) -> None:
    response = client.get("/api/state")

    assert response.status_code == 200
    state = response.get_json()["state"]
    assert state["level"]["id"] == "level_01.json"
    assert state["level"]["solveable"] is True
    assert state["map_size"] == 9
    assert len(state["people"]) == 9
    assert state["flipped"] == [5]
    assert state["initial_flipped"] == [5]
    assert state["remaining"] == 8
    assert state["solved"] is False
    assert state["kb_clauses"] == state["stats"]["initial_clauses"]
    assert state["stats"]["primary"] == 9
    assert state["stats"]["auxiliary"] == 0
    assert state["stats"]["full_clauses"] > state["stats"]["initial_clauses"]
    assert state["stats"]["initial_revealed"] == 1
    assert state["trace"] == []
    assert state["last_auto"] is None
    assert len(state["revealed_clues"]) == 1
    assert state["revealed_clues"][0]["id"] == "CL-5"
    assert state["revealed_clues"][0]["type"] == "EXACTLY"


def test_state_never_exposes_face_down_status_or_clue(client) -> None:
    state = client.get("/api/state").get_json()["state"]

    for person in state["people"]:
        assert person["revealed"] is (person["index"] in state["flipped"])
        if person["revealed"]:
            assert person["status"] in {"CRIMINAL", "INNOCENT"}
            assert person["clue"]["id"] == f"CL-{person['index']}"
        else:
            assert "status" not in person
            assert "clue" not in person


def test_api_load_switches_level(client) -> None:
    response = client.post("/api/load", json={"level_id": "level_02.json"})

    assert response.status_code == 200
    payload = response.get_json()
    state = payload["state"]
    assert state["level"]["id"] == "level_02.json"
    assert state["level"]["number"] == 2
    assert len(state["people"]) == 9
    assert state["flipped"] == state["initial_flipped"]
    assert state["trace"] == []
    assert "Đã mở màn 2" in payload["message"]


def test_api_load_rejects_unknown_level(client) -> None:
    response = client.post("/api/load", json={"level_id": "level_99.json"})

    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"index": "abc", "verdict": "CRIMINAL"},
        {"index": 0, "verdict": "CRIMINAL"},
        {"index": 10, "verdict": "CRIMINAL"},
        {"index": 1, "verdict": "MAYBE"},
        {"index": 5, "verdict": "CRIMINAL"},
    ],
)
def test_api_verdict_rejects_invalid_requests(client, payload) -> None:
    response = client.post("/api/verdict", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert body.get("result") == "ERROR" or "error" in body


def test_api_verdict_not_provable_keeps_state(client) -> None:
    before = client.get("/api/state").get_json()["state"]

    response = client.post(
        "/api/verdict", json={"index": 1, "verdict": "CRIMINAL"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["result"] == "NOT_PROVABLE"
    assert payload["revealed_index"] is None
    after = payload["state"]
    assert after["flipped"] == before["flipped"]
    assert after["trace"] == []


def test_api_verdict_contradicted_keeps_state(client) -> None:
    before = client.get("/api/state").get_json()["state"]

    response = client.post(
        "/api/verdict", json={"index": 8, "verdict": "INNOCENT"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["result"] == "CONTRADICTED"
    assert payload["revealed_index"] is None
    after = payload["state"]
    assert after["flipped"] == before["flipped"]
    assert after["trace"] == []


def test_api_verdict_correct_reveals_card_and_records_trace(client) -> None:
    response = client.post(
        "/api/verdict", json={"index": 8, "verdict": "CRIMINAL"}
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["result"] == "CORRECT"
    assert payload["revealed_index"] == 8
    assert "Heidi" in payload["message"]
    assert "TỘI PHẠM" in payload["message"]

    state = payload["state"]
    assert state["flipped"] == [5, 8]
    assert state["remaining"] == 7
    assert state["solved"] is False
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


def test_api_restart_restores_initial_state(client) -> None:
    client.post("/api/verdict", json={"index": 8, "verdict": "CRIMINAL"})

    response = client.post("/api/restart")

    assert response.status_code == 200
    payload = response.get_json()
    state = payload["state"]
    assert state["flipped"] == [5]
    assert state["initial_flipped"] == [5]
    assert state["remaining"] == 8
    assert state["solved"] is False
    assert state["trace"] == []
    assert state["last_auto"] is None
    assert "trạng thái ban đầu" in payload["message"]


def test_api_hint_returns_forced_person(client) -> None:
    response = client.post("/api/hint")

    assert response.status_code == 200
    payload = response.get_json()
    hint = payload["hint"]
    assert hint is not None
    assert hint["index"] == 8
    assert hint["coord"] == "B3"
    assert hint["name"] == "Heidi"
    assert hint["occupation"] == "Farmer"
    assert hint["icon"] == "mdi--sprout.svg"
    assert hint["clue_ids"] == ["CL-5"]
    assert "Gợi ý" in payload["message"]
    assert payload["state"]["flipped"] == [5]


def test_api_auto_solve_solves_whole_level(client) -> None:
    response = client.post("/api/auto-solve")

    assert response.status_code == 200
    payload = response.get_json()
    summary = payload["summary"]
    assert summary["status"] == "SUCCESS"
    assert summary["waves"] == 7
    assert summary["sat_calls"] > 0
    assert summary["decisions"] >= 0
    assert summary["propagations"] >= 0
    assert summary["backtracks"] >= 0
    assert summary["time_ms"] >= 0.0
    assert summary["final_flipped"] == 9

    state = payload["state"]
    assert state["solved"] is True
    assert state["remaining"] == 0
    assert state["flipped"] == list(range(1, 10))
    assert len(state["trace"]) == 8
    assert state["last_auto"] == summary
    assert all(entry["kind"] == "auto" for entry in state["trace"])
    assert [entry["step"] for entry in state["trace"]] == list(range(1, 9))

    steps = payload["steps"]
    assert len(steps) == 7
    first = steps[0]
    assert first["wave"] == 1
    assert first["active_clue_ids"] == ["CL-5"]
    assert first["new_clue_ids"] == ["CL-8"]
    assert len(first["verdicts"]) == 1
    assert first["verdicts"][0]["index"] == 8
    assert first["verdicts"][0]["status"] == "CRIMINAL"
    assert first["verdicts"][0]["coord"] == "B3"
    assert first["verdicts"][0]["name"] == "Heidi"
    assert first["verdicts"][0]["clue_id"] == "CL-8"
    assert len(first["new_people"]) == 1
    assert first["new_people"][0]["revealed"] is True
    assert first["new_people"][0]["status"] == "CRIMINAL"
    assert first["new_people"][0]["clue"]["id"] == "CL-8"
    assert first["sat_calls"] >= 1
    assert set(first["events"]) == {"PROPAGATION", "DECISION", "BACKTRACK"}
    assert first["kb_clauses_after"] > state["stats"]["initial_clauses"]
    assert steps[-1]["kb_clauses_after"] == state["stats"]["kb_clauses"]


def test_api_auto_solve_twice_is_idempotent(client) -> None:
    first = client.post("/api/auto-solve").get_json()
    second = client.post("/api/auto-solve").get_json()

    assert first["summary"]["status"] == "SUCCESS"
    assert second["summary"]["status"] == "SUCCESS"
    assert second["summary"]["waves"] == 0
    assert second["summary"]["sat_calls"] == 0
    assert second["summary"]["final_flipped"] == 9
    assert second["state"]["solved"] is True


def test_unknown_route_returns_404(client) -> None:
    assert client.get("/api/does-not-exist").status_code == 404


def test_wrong_method_returns_405(client) -> None:
    assert client.get("/api/verdict").status_code == 405
