"""Kiểm thử chín loại manh mối và mã hóa CNF tương ứng.

Mỗi manh mối phải có hai đường kiểm tra độc lập: ``evaluate`` (ngữ nghĩa trực
tiếp) và ``to_cnf`` (mã hóa). Với các vùng nhỏ, kiểm thử duyệt toàn bộ phép
gán để chứng minh hai đường này cho cùng kết quả.
"""

from __future__ import annotations

import pytest

from src.game.clue.clue_type import ClueType
from src.game.clue.concrete_clues.at_least_clue import AtLeastClue
from src.game.clue.concrete_clues.at_most_clue import AtMostClue
from src.game.clue.concrete_clues.compare_clue import CompareClue
from src.game.clue.concrete_clues.different_clue import DifferentClue
from src.game.clue.concrete_clues.exactly_clue import ExactlyClue
from src.game.clue.concrete_clues.fact_clue import FactClue
from src.game.clue.concrete_clues.implies_clue import ImpliesClue
from src.game.clue.concrete_clues.parity_clue import ParityClue
from src.game.clue.concrete_clues.same_clue import SameClue
from tests.helpers import (
    all_assignments,
    cnf_is_satisfiable_with_primary_assignment,
    max_variable,
)


def assert_encoding_matches_semantics(clue) -> None:
    primary_indices = sorted(set(clue.get_region()))
    for assignment in all_assignments(primary_indices):
        expected = clue.evaluate(assignment)
        actual = cnf_is_satisfiable_with_primary_assignment(
            clue.to_cnf(), assignment
        )
        assert actual == expected, (
            clue.get_type(),
            primary_indices,
            assignment,
            expected,
            actual,
        )


def as_set(formula: list[list[int]]) -> set[tuple[int, ...]]:
    return {tuple(clause) for clause in formula}


def test_fact_clue_cnf_and_semantics() -> None:
    criminal = FactClue([1], True)
    innocent = FactClue([1], False)

    assert criminal.to_cnf() == [[1]]
    assert innocent.to_cnf() == [[-1]]
    assert criminal.evaluate({1: True})
    assert not criminal.evaluate({1: False})
    assert innocent.evaluate({1: False})
    assert not innocent.evaluate({1: True})
    assert criminal.get_type() == ClueType.FACT
    assert innocent.get_type() == ClueType.FACT


def test_same_clue_cnf_and_semantics() -> None:
    clue = SameClue([1, 2])

    assert as_set(clue.to_cnf()) == {(-1, 2), (1, -2)}
    assert clue.evaluate({1: True, 2: True})
    assert clue.evaluate({1: False, 2: False})
    assert not clue.evaluate({1: True, 2: False})
    assert not clue.evaluate({1: False, 2: True})
    assert clue.get_type() == ClueType.SAME


def test_different_clue_cnf_and_semantics() -> None:
    clue = DifferentClue([1, 2])

    assert as_set(clue.to_cnf()) == {(1, 2), (-1, -2)}
    assert not clue.evaluate({1: True, 2: True})
    assert not clue.evaluate({1: False, 2: False})
    assert clue.evaluate({1: True, 2: False})
    assert clue.evaluate({1: False, 2: True})
    assert clue.get_type() == ClueType.DIFFERENT


def test_at_least_clue_cnf_and_semantics() -> None:
    clue = AtLeastClue([1, 2, 3], 2)

    assert as_set(clue.to_cnf()) == {(1, 2), (1, 3), (2, 3)}
    assert clue.evaluate({1: True, 2: True, 3: False})
    assert clue.evaluate({1: True, 2: True, 3: True})
    assert not clue.evaluate({1: True, 2: False, 3: False})
    assert clue.get_type() == ClueType.AT_LEAST


def test_at_most_clue_cnf_and_semantics() -> None:
    clue = AtMostClue([1, 2, 3], 1)

    assert as_set(clue.to_cnf()) == {(-1, -2), (-1, -3), (-2, -3)}
    assert clue.evaluate({1: True, 2: False, 3: False})
    assert clue.evaluate({1: False, 2: False, 3: False})
    assert not clue.evaluate({1: True, 2: True, 3: False})
    assert clue.get_type() == ClueType.AT_MOST


def test_exactly_clue_cnf_and_semantics() -> None:
    clue = ExactlyClue([1, 2, 3], 2)

    assert as_set(clue.to_cnf()) == {
        (-1, -2, -3),
        (1, 2),
        (1, 3),
        (2, 3),
    }
    assert clue.evaluate({1: True, 2: True, 3: False})
    assert not clue.evaluate({1: True, 2: False, 3: False})
    assert not clue.evaluate({1: True, 2: True, 3: True})
    assert clue.get_type() == ClueType.EXACTLY


def test_counting_clue_boundary_values() -> None:
    assert AtLeastClue([1, 2, 3], 0).to_cnf() == []
    assert AtMostClue([1, 2, 3], 3).to_cnf() == []
    assert as_set(ExactlyClue([1, 2, 3], 0).to_cnf()) == {
        (-1,),
        (-2,),
        (-3,),
    }
    assert as_set(ExactlyClue([1, 2, 3], 3).to_cnf()) == {
        (1,),
        (2,),
        (3,),
    }


def test_compare_clue_equal_regions_cnf() -> None:
    equal = CompareClue([1, 2], [2, 3], True)

    assert as_set(equal.to_cnf()) == {(-1, 3), (1, -3)}
    assert equal.evaluate({1: True, 2: True, 3: True})
    assert equal.evaluate({1: False, 2: True, 3: False})
    assert not equal.evaluate({1: True, 2: True, 3: False})


def test_compare_clue_identical_regions_is_tautology_or_contradiction() -> None:
    tautology = CompareClue([1, 2], [1, 2], True)
    contradiction = CompareClue([1, 2], [1, 2], False)

    assert tautology.to_cnf() == []
    assert tautology.evaluate({1: True, 2: False})
    assert tautology.evaluate({1: False, 2: False})

    assert contradiction.to_cnf() == [[]]
    assert not contradiction.evaluate({1: True, 2: False})
    assert not contradiction.evaluate({1: False, 2: False})


def test_compare_clue_more_than() -> None:
    clue = CompareClue([1, 2], [2, 3], False)

    assert clue.evaluate({1: True, 2: True, 3: False})
    assert not clue.evaluate({1: False, 2: True, 3: False})
    assert not clue.evaluate({1: True, 2: True, 3: True})
    assert_encoding_matches_semantics(clue)


def test_parity_clue_cnf_and_semantics() -> None:
    clue = ParityClue([1, 2], True)
    clue.set_first_auxiliary_index(3)

    assert clue.get_auxiliary_count() == 1
    assert as_set(clue.to_cnf()) == {
        (-1, -2, -3),
        (1, 2, -3),
        (1, -2, 3),
        (-1, 2, 3),
        (3,),
    }
    assert clue.evaluate({1: True, 2: False})
    assert clue.evaluate({1: False, 2: True})
    assert not clue.evaluate({1: True, 2: True})
    assert not clue.evaluate({1: False, 2: False})
    assert clue.get_type() == ClueType.PARITY


def test_parity_clue_requires_auxiliary_index() -> None:
    clue = ParityClue([1, 2, 3], True)

    with pytest.raises(AssertionError):
        clue.to_cnf()

    clue.set_first_auxiliary_index(4)
    formula = clue.to_cnf()

    assert formula
    assert max_variable(formula) == 5
    assert clue.get_auxiliary_count() == 2


def test_implies_clue_cnf_and_semantics() -> None:
    clue = ImpliesClue([1], True, FactClue([2], True))

    assert clue.to_cnf() == [[-1, 2]]
    assert clue.evaluate({1: True, 2: True})
    assert not clue.evaluate({1: True, 2: False})
    assert clue.evaluate({1: False, 2: False})
    assert clue.get_type() == ClueType.IMPLIES


def test_implies_clue_with_negative_premise() -> None:
    clue = ImpliesClue([1], False, FactClue([2], True))

    assert clue.to_cnf() == [[1, 2]]
    assert clue.evaluate({1: False, 2: True})
    assert not clue.evaluate({1: False, 2: False})
    assert clue.evaluate({1: True, 2: False})


def test_implies_clue_with_binary_conclusion() -> None:
    clue = ImpliesClue([1], True, SameClue([2, 3]))

    assert as_set(clue.to_cnf()) == {
        (-1, -2, 3),
        (-1, 2, -3),
    }
    assert_encoding_matches_semantics(clue)


def test_implies_clue_with_parity_conclusion_uses_auxiliary_variables() -> None:
    conclusion = ParityClue([2, 3, 4], True)
    clue = ImpliesClue([1], True, conclusion)
    clue.set_first_auxiliary_index(5)

    assert clue.get_auxiliary_count() == 2
    assert conclusion.first_auxiliary_index == 5
    assert_encoding_matches_semantics(clue)


@pytest.mark.parametrize(
    "clue",
    [
        FactClue([1], True),
        SameClue([1, 2]),
        DifferentClue([1, 2]),
        AtLeastClue([1, 2, 3], 1),
        AtMostClue([1, 2, 3], 2),
        ExactlyClue([1, 2, 3], 2),
        CompareClue([1, 2], [2, 3], True),
        CompareClue([1, 2], [3, 4], False),
        ImpliesClue([1], True, ExactlyClue([2, 3, 4], 2)),
    ],
)
def test_encoding_matches_semantics_for_non_auxiliary_clues(clue) -> None:
    assert_encoding_matches_semantics(clue)


def test_encoding_matches_semantics_for_parity() -> None:
    clue = ParityClue([1, 2, 3], True)
    clue.set_first_auxiliary_index(4)

    assert_encoding_matches_semantics(clue)


def test_get_region_for_compare_and_implies() -> None:
    compare = CompareClue([1, 2], [2, 3], True)
    implies = ImpliesClue([1], True, SameClue([2, 3]))

    assert compare.get_region() == [1, 2, 2, 3]
    assert set(implies.get_region()) == {1, 2, 3}
    assert len(implies.get_region()) == 3


def test_auxiliary_counts() -> None:
    assert FactClue([1], True).get_auxiliary_count() == 0
    assert SameClue([1, 2]).get_auxiliary_count() == 0
    assert DifferentClue([1, 2]).get_auxiliary_count() == 0
    assert AtLeastClue([1, 2], 1).get_auxiliary_count() == 0
    assert AtMostClue([1, 2], 1).get_auxiliary_count() == 0
    assert ExactlyClue([1, 2], 1).get_auxiliary_count() == 0
    assert CompareClue([1, 2], [3, 4], True).get_auxiliary_count() == 0
    assert ParityClue([1, 2, 3, 4], True).get_auxiliary_count() == 3
    assert (
        ImpliesClue([1], True, ParityClue([2, 3, 4], True)).get_auxiliary_count()
        == 2
    )


def test_is_valid_with_map_for_all_clue_types() -> None:
    assert FactClue([1], True).is_valid_with_map(1)
    assert not FactClue([1], True).is_valid_with_map(0)
    assert not FactClue([2], True).is_valid_with_map(1)

    assert SameClue([1, 2]).is_valid_with_map(2)
    assert not SameClue([1, 2]).is_valid_with_map(1)
    assert not SameClue([1, 1]).is_valid_with_map(2)

    assert DifferentClue([1, 2]).is_valid_with_map(2)
    assert not DifferentClue([1, 2]).is_valid_with_map(1)
    assert not DifferentClue([1, 1]).is_valid_with_map(2)

    assert AtLeastClue([1, 2, 3], 1).is_valid_with_map(3)
    assert not AtLeastClue([1, 2, 3], 1).is_valid_with_map(2)
    assert not AtLeastClue([0, 1, 2], 1).is_valid_with_map(3)

    assert AtMostClue([1, 2, 3], 1).is_valid_with_map(3)
    assert not AtMostClue([1, 2, 3], 1).is_valid_with_map(2)

    assert ExactlyClue([1, 2, 3], 1).is_valid_with_map(3)
    assert not ExactlyClue([1, 2, 3], 1).is_valid_with_map(2)

    assert CompareClue([1, 2], [2, 3], True).is_valid_with_map(3)
    assert not CompareClue([1, 2], [2, 3], True).is_valid_with_map(2)
    assert not CompareClue([1, 2], [0, 3], True).is_valid_with_map(3)

    assert ParityClue([1, 2], True).is_valid_with_map(2)
    assert not ParityClue([1, 2], True).is_valid_with_map(1)

    assert ImpliesClue([1], True, FactClue([2], True)).is_valid_with_map(2)
    assert not ImpliesClue([1], True, FactClue([2], True)).is_valid_with_map(1)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: FactClue([], True),
        lambda: FactClue([1, 2], True),
        lambda: SameClue([1]),
        lambda: SameClue([1, 2, 3]),
        lambda: DifferentClue([1]),
        lambda: DifferentClue([1, 2, 3]),
        lambda: AtLeastClue([], 0),
        lambda: AtLeastClue([1, 2], -1),
        lambda: AtLeastClue([1, 2], 3),
        lambda: AtLeastClue([1, 1], 1),
        lambda: AtMostClue([], 0),
        lambda: AtMostClue([1, 2], -1),
        lambda: AtMostClue([1, 2], 3),
        lambda: AtMostClue([1, 1], 1),
        lambda: ExactlyClue([], 0),
        lambda: ExactlyClue([1, 2], -1),
        lambda: ExactlyClue([1, 2], 3),
        lambda: ExactlyClue([1, 1], 1),
        lambda: CompareClue([], [1], True),
        lambda: CompareClue([1], [], True),
        lambda: CompareClue([1, 1], [2], True),
        lambda: CompareClue([1], [2, 2], True),
        lambda: ParityClue([], True),
        lambda: ParityClue([1, 1], True),
        lambda: ImpliesClue([1, 2], True, FactClue([3], True)),
    ],
)
def test_invalid_clue_parameters_raise_assertion(factory) -> None:
    with pytest.raises(AssertionError):
        factory()
