"""Kiểm thử DPLL SAT solver.

Các kiểm thử tập trung vào bốn yêu cầu của mục 4.3: lan truyền đơn vị, phát
hiện mâu thuẫn, chọn biến tất định, và quay lui. Ngoài ra, kết quả SAT phải
kèm một phép gán đầy đủ thỏa mãn công thức.
"""

from __future__ import annotations

import pytest

from src.game.core.core_types.SAT_solve_result import SATSolveEvent
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from tests.helpers import brute_force_models, is_cnf_satisfied


def event_types(events):
    return [event for event, _ in events]


def test_empty_formula_is_sat_with_all_false_assignment() -> None:
    solver = DpllSatSolver(3)

    result = solver.SAT_solve([])

    assert result.is_SAT
    assert result.confirmed_literals == []
    assert result.possible_assignment == {1: False, 2: False, 3: False}
    assert result.events == []


def test_single_unit_clause_is_propagated() -> None:
    solver = DpllSatSolver(2)

    result = solver.SAT_solve([[2]])

    assert result.is_SAT
    assert result.confirmed_literals == [2]
    assert result.possible_assignment is not None
    assert result.possible_assignment[2] is True
    assert result.events == [(SATSolveEvent.PROPAGATION, 2)]


def test_contradictory_unit_clauses_are_unsat() -> None:
    solver = DpllSatSolver(1)

    result = solver.SAT_solve([[1], [-1]])

    assert not result.is_SAT
    assert result.confirmed_literals is None
    assert result.possible_assignment is None
    assert event_types(result.events) == [SATSolveEvent.PROPAGATION]


def test_empty_clause_is_unsat() -> None:
    solver = DpllSatSolver(1)

    result = solver.SAT_solve([[]])

    assert not result.is_SAT
    assert result.events == []


def test_unit_propagation_chain() -> None:
    solver = DpllSatSolver(3)

    result = solver.SAT_solve([[1], [-1, 2], [-2, 3]])

    assert result.is_SAT
    assert result.confirmed_literals == [1, 2, 3]
    assert result.possible_assignment == {1: True, 2: True, 3: True}


def test_branching_backtracks_and_then_finds_model() -> None:
    solver = DpllSatSolver(2)

    result = solver.SAT_solve([[-1, 2], [-1, -2], [1, 2]])

    assert result.is_SAT
    assert result.possible_assignment == {1: False, 2: True}
    assert (SATSolveEvent.DECISION, 1) in result.events
    assert (SATSolveEvent.BACKTRACK, 1) in result.events
    assert (SATSolveEvent.DECISION, -1) in result.events


def test_variable_selection_is_deterministic() -> None:
    solver = DpllSatSolver(4)

    result = solver.SAT_solve([[3, 4], [2, -3]])

    assert result.is_SAT
    assert result.events[0] == (SATSolveEvent.DECISION, 2)


def test_sat_assignment_is_complete_and_satisfies_formula() -> None:
    solver = DpllSatSolver(4)
    formula = [[1, 2], [-1, 2]]

    result = solver.SAT_solve(formula)

    assert result.is_SAT
    assert result.possible_assignment is not None
    assert set(result.possible_assignment) == {1, 2, 3, 4}
    assert is_cnf_satisfied(formula, result.possible_assignment)


def test_map_size_zero_returns_empty_assignment() -> None:
    solver = DpllSatSolver(0)

    result = solver.SAT_solve([[1]])

    assert result.is_SAT
    assert result.confirmed_literals == [1]
    assert result.possible_assignment == {}


def test_events_are_reset_between_solves() -> None:
    solver = DpllSatSolver(2)

    first = solver.SAT_solve([[1]])
    second = solver.SAT_solve([[2]])

    assert first.events == [(SATSolveEvent.PROPAGATION, 1)]
    assert second.events == [(SATSolveEvent.PROPAGATION, 2)]


def test_solve_with_time_returns_non_negative_duration() -> None:
    solver = DpllSatSolver(2)

    result, elapsed = solver.SAT_solve_with_time([[1, 2]])

    assert result.is_SAT
    assert elapsed >= 0.0


def test_confirmed_literals_are_logically_entailed() -> None:
    solver = DpllSatSolver(2)
    formula = [[2], [1, 2], [-1, 2]]

    result = solver.SAT_solve(formula)

    assert result.is_SAT
    assert result.confirmed_literals == [2]
    models = list(brute_force_models(formula, 2))
    assert models
    for literal in result.confirmed_literals:
        for model in models:
            assert model[abs(literal)] == (literal > 0)


def test_unsat_result_has_no_assignment() -> None:
    solver = DpllSatSolver(2)

    result = solver.SAT_solve([[1], [-1]])

    assert not result.is_SAT
    assert result.confirmed_literals is None
    assert result.possible_assignment is None


def test_unsat_formula_requiring_nested_search() -> None:
    solver = DpllSatSolver(3)
    clauses = [
        [1, 2, 3],
        [1, 2, -3],
        [1, -2, 3],
        [1, -2, -3],
        [-1, 2, 3],
        [-1, 2, -3],
        [-1, -2, 3],
        [-1, -2, -3],
    ]

    result = solver.SAT_solve(clauses)

    assert not result.is_SAT
    assert result.confirmed_literals is None
    assert result.possible_assignment is None
    assert (SATSolveEvent.DECISION, 1) in result.events
    assert (SATSolveEvent.BACKTRACK, 1) in result.events


@pytest.mark.parametrize(
    "formula",
    [
        [],
        [[1]],
        [[1, 2], [-1, 2]],
        [[1, 2], [-1, -2]],
        [[1], [-1]],
        [[1, 2, 3], [-1], [-2]],
        [[1, -2], [2, 3], [-3, 1]],
    ],
)
def test_sat_models_are_valid(formula: list[list[int]]) -> None:
    solver = DpllSatSolver(3)

    result = solver.SAT_solve(formula)

    if result.is_SAT:
        assert result.possible_assignment is not None
        assert is_cnf_satisfied(formula, result.possible_assignment)
    else:
        assert not any(brute_force_models(formula, 3))
