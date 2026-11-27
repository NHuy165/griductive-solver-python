"""Kiểm thử ``LogicAgent``: phân loại, kiểm tra duy nhất và vòng suy luận.

Điểm quan trọng nhất là agent chỉ kết luận khi trạng thái được suy ra từ KB
công khai. Kiểm thử mô phỏng lại từng bước và xác nhận mọi phán quyết đều
được entailed, không có phán đoán mò.
"""

from __future__ import annotations

import pytest

from src.game.core.core_types.entailment_check_result import EntailmentCheckStatus
from src.game.core.core_types.exceptions import ExceptionBrokenClues
from src.game.core.core_types.level_solve_result import LevelSolveStatus
from src.game.logic.game_engine import GameEngine
from src.game.logic.logic_agent import LogicAgent
from tests.helpers import (
    build_complete_knowledge_base,
    build_full_formula,
    clause_counter,
    hidden_solution,
    is_sat,
    max_variable,
)


def test_assign_from_formula_confirms_units_by_propagation(agent: LogicAgent) -> None:
    result = agent.assign_from_formula([[1], [-1, 2]])

    assert result.successful
    assert result.non_auxi_indices_confirmed_propagation == [1, 2]
    assert result.non_auxi_indices_confirmed_entailment == []
    assert result.non_auxi_indices_unknown_entailment == []
    assert result.confirmed_assignments == {1: True, 2: True}
    assert result.events_in_entailment_checks == {}


def test_assign_from_formula_confirms_forced_values_by_entailment(
    agent: LogicAgent,
) -> None:
    result = agent.assign_from_formula(
        [[1], [2, 3], [2, -3], [-2, 3]]
    )

    assert result.successful
    assert result.non_auxi_indices_confirmed_propagation == [1]
    assert result.non_auxi_indices_confirmed_entailment == [2, 3]
    assert result.non_auxi_indices_unknown_entailment == []
    assert result.confirmed_assignments == {1: True, 2: True, 3: True}
    assert set(result.events_in_entailment_checks) == {2, 3}


def test_assign_from_formula_keeps_ambiguous_values_unknown(agent: LogicAgent) -> None:
    result = agent.assign_from_formula([[1, 2], [-1, -2]])

    assert result.successful
    assert result.non_auxi_indices_confirmed_propagation == []
    assert result.non_auxi_indices_confirmed_entailment == []
    assert result.non_auxi_indices_unknown_entailment == [1, 2]
    assert result.confirmed_assignments == {}
    assert set(result.events_in_entailment_checks) == {1, 2}


def test_assign_from_formula_reports_inconsistency(agent: LogicAgent) -> None:
    result = agent.assign_from_formula([[1], [-1]])

    assert not result.successful
    assert result.non_auxi_indices_confirmed_propagation == []
    assert result.non_auxi_indices_confirmed_entailment == []
    assert result.non_auxi_indices_unknown_entailment == []
    assert result.confirmed_assignments == {}
    assert result.events_in_entailment_checks == {}


def test_assign_from_formula_requires_primary_variables(agent: LogicAgent) -> None:
    with pytest.raises(AssertionError):
        agent.assign_from_formula([])


def test_assign_from_formula_with_time(agent: LogicAgent, engine: GameEngine) -> None:
    result, elapsed = agent.assign_from_formula_with_time(
        engine.get_initial_formula()
    )

    assert result.successful
    assert result.confirmed_assignments == {5: True, 8: True}
    assert elapsed >= 0.0


def test_unique_check_accepts_full_level_formula(agent: LogicAgent, level_01) -> None:
    assert agent.unique_check(build_full_formula(level_01))


def test_unique_check_rejects_ambiguous_formula(agent: LogicAgent) -> None:
    assert not agent.unique_check([[1, 2]])


def test_unique_check_rejects_unsatisfiable_formula(agent: LogicAgent) -> None:
    assert not agent.unique_check([[1], [-1]])


def test_solve_level_success_and_every_verdict_is_entailed(
    agent: LogicAgent, engine: GameEngine, level_01
) -> None:
    result = agent.solve_level()
    hidden = hidden_solution(level_01)
    steps = result.solve_steps

    assert result.status == LevelSolveStatus.SUCCESS
    assert result.final_assignment == hidden
    assert len(steps) == 7
    assert sum(
        len(step.assignment_result.confirmed_assignments) for step in steps
    ) == 8

    previous_formula = engine.get_initial_formula()
    previous_flipped = engine.get_initially_revealed_region()
    map_size = max(9, max_variable(previous_formula))

    for step_index, step in enumerate(steps):
        assert clause_counter(step.current_formula) == clause_counter(
            previous_formula
        )
        assert step.current_indices_flipped == previous_flipped
        assert is_sat(step.current_formula, map_size)

        confirmed = step.assignment_result.confirmed_assignments
        assert confirmed
        assert len(step.revealed_clues) == len(confirmed)

        for index, is_criminal in confirmed.items():
            assert index not in previous_flipped
            assert is_criminal is hidden[index]
            opposite = -index if is_criminal else index
            assert not is_sat(step.current_formula + [[opposite]], map_size)

        expected_formula = list(previous_formula)
        for index, is_criminal in confirmed.items():
            expected_formula.append([index] if is_criminal else [-index])

        for (index, _), clue in zip(confirmed.items(), step.revealed_clues):
            assert clue is level_01.get_person(index).get_clue()
            assert clue.evaluate(hidden)
            expected_formula.extend(clue.to_cnf())

        if step_index + 1 < len(steps):
            assert clause_counter(steps[step_index + 1].current_formula) == (
                clause_counter(expected_formula)
            )

        previous_formula = expected_formula
        previous_flipped = previous_flipped | set(confirmed)

    assert previous_flipped == set(range(1, 10))
    assert clause_counter(previous_formula) == clause_counter(
        build_complete_knowledge_base(level_01)
    )


def test_solve_from_initial_state_matches_solve_level(
    agent: LogicAgent, engine: GameEngine
) -> None:
    result = agent.solve_from_state(
        engine.get_initial_formula(),
        engine.get_initially_revealed_region(),
        engine.get_initially_revealed_assignments(),
    )

    assert result.status == LevelSolveStatus.SUCCESS
    assert len(result.solve_steps) == 7


def test_solve_from_state_reports_stuck(agent: LogicAgent) -> None:
    result = agent.solve_from_state([[1, 2]], set(), {})

    assert result.status == LevelSolveStatus.STUCK
    assert result.final_assignment == {}
    assert len(result.solve_steps) == 1
    assert result.solve_steps[0].assignment_result.confirmed_assignments == {}
    assert result.solve_steps[0].revealed_clues == []


def test_solve_from_state_reports_inconsistent(agent: LogicAgent) -> None:
    result = agent.solve_from_state([[1], [-1]], set(), {})

    assert result.status == LevelSolveStatus.INCONSISTENT
    assert result.final_assignment == {}
    assert len(result.solve_steps) == 1
    assert not result.solve_steps[0].assignment_result.successful


def test_get_hint_returns_a_forced_unflipped_index(
    agent: LogicAgent, engine: GameEngine
) -> None:
    hint = agent.get_hint(
        engine.get_initial_formula(),
        engine.get_initially_revealed_region(),
    )

    assert hint == 8


def test_get_hint_raises_when_nothing_is_forced(agent: LogicAgent) -> None:
    with pytest.raises(ExceptionBrokenClues):
        agent.get_hint([[1, 2]], set())


def test_get_hint_raises_when_every_formula_index_is_flipped(
    agent: LogicAgent,
) -> None:
    with pytest.raises(ExceptionBrokenClues):
        agent.get_hint([[1]], {1})


def test_get_hint_raises_when_clues_are_contradictory(
    agent: LogicAgent,
) -> None:
    with pytest.raises(ExceptionBrokenClues):
        agent.get_hint([[1], [-1]], set())


def test_get_hint_raises_when_level_is_solved(
    agent: LogicAgent, level_01
) -> None:
    with pytest.raises(AssertionError):
        agent.get_hint(
            build_full_formula(level_01),
            set(range(1, 10)),
        )


def test_agent_follows_public_formula_not_hidden_status(agent: LogicAgent) -> None:
    result = agent.assign_from_formula([[-8]])

    assert result.successful
    assert result.confirmed_assignments == {8: False}


def test_solve_level_with_time_returns_duration(
    agent: LogicAgent,
) -> None:
    result, elapsed = agent.solve_level_with_time()

    assert result.status == LevelSolveStatus.SUCCESS
    assert elapsed >= 0.0


def test_entailment_check_status_values() -> None:
    assert EntailmentCheckStatus.CRIMINAL.value == "CRIMINAL"
    assert EntailmentCheckStatus.INNOCENT.value == "INNOCENT"
    assert EntailmentCheckStatus.UNKNOWN.value == "UNKNOWN"
