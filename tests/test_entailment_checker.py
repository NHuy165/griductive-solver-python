"""Kiểm thử trực tiếp ``EntailmentChecker``.

Lớp này là cầu nối giữa LogicAgent và DPLL: nó thêm phủ định của một literal
rồi phân loại người đó là CRIMINAL, INNOCENT hoặc UNKNOWN.
"""

from __future__ import annotations

from src.game.core.core_types.entailment_check_result import (
    EntailmentCheckStatus,
)
from src.game.logic.entailment_checker import EntailmentChecker


def test_forced_criminal_is_classified_as_criminal() -> None:
    formula = [[1, 2], [-1, 2]]

    result = EntailmentChecker.entailment_check(
        formula,
        2,
        was_criminal_in_one_possible_assignment=True,
    )

    assert result.status == EntailmentCheckStatus.CRIMINAL
    assert isinstance(result.events, list)
    assert result.events


def test_forced_innocent_is_classified_as_innocent() -> None:
    formula = [[1, -2], [-1, -2]]

    result = EntailmentChecker.entailment_check(
        formula,
        2,
        was_criminal_in_one_possible_assignment=False,
    )

    assert result.status == EntailmentCheckStatus.INNOCENT
    assert result.events


def test_ambiguous_value_is_classified_as_unknown() -> None:
    formula = [[1, 2], [-1, 2]]

    result = EntailmentChecker.entailment_check(
        formula,
        1,
        was_criminal_in_one_possible_assignment=True,
    )

    assert result.status == EntailmentCheckStatus.UNKNOWN
    assert result.events


def test_unknown_status_for_both_possible_values() -> None:
    formula = [[1, 2], [-1, -2]]

    first = EntailmentChecker.entailment_check(
        formula,
        1,
        was_criminal_in_one_possible_assignment=True,
    )
    second = EntailmentChecker.entailment_check(
        formula,
        1,
        was_criminal_in_one_possible_assignment=False,
    )

    assert first.status == EntailmentCheckStatus.UNKNOWN
    assert second.status == EntailmentCheckStatus.UNKNOWN


def test_entailment_check_does_not_mutate_formula() -> None:
    formula = [[1, 2], [-1, 2]]

    EntailmentChecker.entailment_check(
        formula,
        2,
        was_criminal_in_one_possible_assignment=True,
    )

    assert formula == [[1, 2], [-1, 2]]
