"""Kiểm thử các kiểu dữ liệu lõi và các bất biến của chúng."""

from __future__ import annotations

import pytest

from src.game.clue.clue_type import ClueType
from src.game.core.core_types.assignment_result import AssignmentResult
from src.game.core.core_types.entailment_check_result import (
    EntailmentCheckStatus,
)
from src.game.core.core_types.exceptions import (
    ExceptionBrokenClues,
    ExceptionInvalidLevel,
)
from src.game.core.core_types.level_solve_result import (
    LevelSolveStatus,
    LevelSolveStepResult,
)
from src.game.core.core_types.SAT_solve_result import SATSolveEvent
from src.game.core.core_types.verdict_result import VerdictResult


def test_assignment_result_rejects_mismatched_event_count() -> None:
    with pytest.raises(AssertionError):
        AssignmentResult(
            non_auxi_indices_confirmed_propagation=[1],
            non_auxi_indices_confirmed_entailment=[2],
            non_auxi_indices_unknown_entailment=[3],
            events_to_reach_possible_assignment=[],
            events_in_entailment_checks={2: []},
            confirmed_assignments={1: True},
            successful=True,
        )


def test_level_solve_step_requires_one_clue_per_verdict() -> None:
    assignment_result = AssignmentResult(
        non_auxi_indices_confirmed_propagation=[],
        non_auxi_indices_confirmed_entailment=[],
        non_auxi_indices_unknown_entailment=[],
        events_to_reach_possible_assignment=[],
        events_in_entailment_checks={},
        confirmed_assignments={1: True},
        successful=True,
    )

    with pytest.raises(AssertionError):
        LevelSolveStepResult(
            current_formula=[],
            current_indices_flipped=set(),
            assignment_result=assignment_result,
            revealed_clues=[],
        )


def test_enum_values() -> None:
    assert ClueType.FACT.value == "FACT"
    assert ClueType.SAME.value == "SAME"
    assert ClueType.DIFFERENT.value == "DIFFERENT"
    assert ClueType.EXACTLY.value == "EXACTLY"
    assert ClueType.AT_LEAST.value == "AT_LEAST"
    assert ClueType.AT_MOST.value == "AT_MOST"
    assert ClueType.IMPLIES.value == "IMPLIES"
    assert ClueType.COMPARE.value == "COMPARE"
    assert ClueType.PARITY.value == "PARITY"

    assert SATSolveEvent.PROPAGATION.value == "PROPAGATION"
    assert SATSolveEvent.DECISION.value == "DECISION"
    assert SATSolveEvent.BACKTRACK.value == "BACKTRACK"

    assert EntailmentCheckStatus.CRIMINAL.value == "CRIMINAL"
    assert EntailmentCheckStatus.INNOCENT.value == "INNOCENT"
    assert EntailmentCheckStatus.UNKNOWN.value == "UNKNOWN"

    assert VerdictResult.CORRECT.value == "CORRECT"
    assert VerdictResult.CONTRADICTED.value == "CONTRADICTED"
    assert VerdictResult.NOT_PROVABLE.value == "NOT_PROVABLE"

    assert LevelSolveStatus.SUCCESS.value == "SUCCESS"
    assert LevelSolveStatus.STUCK.value == "STUCK"
    assert LevelSolveStatus.INCONSISTENT.value == "INCONSISTENT"


def test_exception_hierarchy() -> None:
    assert issubclass(ExceptionBrokenClues, Exception)
    assert issubclass(ExceptionInvalidLevel, Exception)
