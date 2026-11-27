"""Kiểm thử các hàm đo lường dùng cho thí nghiệm mục 4.5."""

from __future__ import annotations

from src.game.clue.concrete_clues.at_least_clue import AtLeastClue
from src.game.clue.concrete_clues.fact_clue import FactClue
from src.game.core.core_types.assignment_result import AssignmentResult
from src.game.core.core_types.level_solve_result import (
    LevelSolveResult,
    LevelSolveStatus,
    LevelSolveStepResult,
)
from src.game.core.core_types.SAT_solve_result import (
    SATSolveEvent,
    SATSolveResult,
)
from src.game.logic.game_engine import GameEngine
from src.game.metrics.SAT_solves import (
    count_SAT_solves_from_assignment_result,
    count_SAT_solves_from_level_solve,
)
from src.game.metrics.cnf_clauses import (
    count_cnf_clauses_from_formula,
    count_cnf_clauses_generated_at_step,
)
from src.game.metrics.events import (
    count_events,
    count_events_from_assignment_result,
    count_events_from_SAT_solve,
)
from src.game.metrics.level_solve_steps import (
    count_reveal_waves_from_level_solve,
)
from src.game.metrics.primary_auxiliary_variables import (
    count_primary_auxiliary_indices,
)


def sample_assignment_result() -> AssignmentResult:
    return AssignmentResult(
        non_auxi_indices_confirmed_propagation=[1],
        non_auxi_indices_confirmed_entailment=[2],
        non_auxi_indices_unknown_entailment=[3],
        events_to_reach_possible_assignment=[
            (SATSolveEvent.DECISION, 1),
            (SATSolveEvent.PROPAGATION, 2),
        ],
        events_in_entailment_checks={
            2: [(SATSolveEvent.PROPAGATION, -2)],
            3: [
                (SATSolveEvent.DECISION, 3),
                (SATSolveEvent.BACKTRACK, 3),
            ],
        },
        confirmed_assignments={1: True, 2: False},
        successful=True,
    )


def sample_step() -> LevelSolveStepResult:
    return LevelSolveStepResult(
        current_formula=[],
        current_indices_flipped=set(),
        assignment_result=sample_assignment_result(),
        revealed_clues=[
            FactClue([1], True),
            FactClue([2], False),
        ],
    )


def test_count_events() -> None:
    events = [
        (SATSolveEvent.PROPAGATION, 1),
        (SATSolveEvent.PROPAGATION, 2),
        (SATSolveEvent.DECISION, 3),
        (SATSolveEvent.BACKTRACK, 3),
    ]

    assert count_events(events) == {
        SATSolveEvent.PROPAGATION: 2,
        SATSolveEvent.DECISION: 1,
        SATSolveEvent.BACKTRACK: 1,
    }


def test_count_events_from_sat_solve() -> None:
    result = SATSolveResult(
        is_SAT=True,
        confirmed_literals=[1],
        possible_assignment={1: True},
        events=[
            (SATSolveEvent.PROPAGATION, 1),
            (SATSolveEvent.DECISION, 2),
        ],
    )

    assert count_events_from_SAT_solve(result) == {
        SATSolveEvent.PROPAGATION: 1,
        SATSolveEvent.DECISION: 1,
        SATSolveEvent.BACKTRACK: 0,
    }


def test_count_events_from_assignment_result() -> None:
    assert count_events_from_assignment_result(sample_assignment_result()) == {
        SATSolveEvent.PROPAGATION: 2,
        SATSolveEvent.DECISION: 2,
        SATSolveEvent.BACKTRACK: 1,
    }


def test_count_events_from_unsuccessful_assignment_result() -> None:
    result = AssignmentResult([], [], [], [], {}, {}, False)

    assert count_events_from_assignment_result(result) == {
        SATSolveEvent.PROPAGATION: 0,
        SATSolveEvent.DECISION: 0,
        SATSolveEvent.BACKTRACK: 0,
    }


def test_count_sat_solves_from_assignment_result() -> None:
    assert count_SAT_solves_from_assignment_result(
        sample_assignment_result()
    ) == 3


def test_count_sat_solves_from_unsuccessful_assignment_result() -> None:
    result = AssignmentResult([], [], [], [], {}, {}, False)

    assert count_SAT_solves_from_assignment_result(result) == 1


def test_count_sat_solves_from_level_solve() -> None:
    result = LevelSolveResult(
        status=LevelSolveStatus.SUCCESS,
        final_assignment={1: True, 2: False},
        solve_steps=[sample_step(), sample_step()],
    )

    assert count_SAT_solves_from_level_solve(result) == 6


def test_count_sat_solves_from_empty_level_solve() -> None:
    result = LevelSolveResult(
        status=LevelSolveStatus.SUCCESS,
        final_assignment={},
        solve_steps=[],
    )

    assert count_SAT_solves_from_level_solve(result) == 0


def test_count_cnf_clauses_from_formula() -> None:
    assert count_cnf_clauses_from_formula([[1], [-1, 2], [3]]) == 3
    assert count_cnf_clauses_from_formula([]) == 0


def test_count_cnf_clauses_generated_at_step() -> None:
    step = LevelSolveStepResult(
        current_formula=[],
        current_indices_flipped=set(),
        assignment_result=sample_assignment_result(),
        revealed_clues=[
            FactClue([1], True),
            AtLeastClue([1, 2], 1),
        ],
    )

    assert count_cnf_clauses_generated_at_step(step) == 2


def test_count_reveal_waves() -> None:
    result = LevelSolveResult(
        status=LevelSolveStatus.SUCCESS,
        final_assignment={},
        solve_steps=[sample_step(), sample_step()],
    )

    assert count_reveal_waves_from_level_solve(result) == 2


def test_count_primary_auxiliary_variables(engine: GameEngine) -> None:
    assert count_primary_auxiliary_indices(engine) == (9, 0)
