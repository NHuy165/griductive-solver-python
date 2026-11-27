"""Kiểm thử ``GameEngine``: trạng thái công khai và phán quyết.

Engine chỉ được dùng thông tin công khai khi kiểm tra một phán quyết. Các
kiểm thử dùng công thức nhỏ để kiểm soát chính xác kết quả CORRECT,
CONTRADICTED, NOT_PROVABLE và lỗi khi KB mâu thuẫn.
"""

from __future__ import annotations

import pytest

from src.game.core.core_types.exceptions import ExceptionBrokenClues
from src.game.core.core_types.verdict_result import VerdictResult
from src.game.logic.game_engine import GameEngine
from tests.helpers import (
    build_initial_formula,
    clause_counter,
    is_sat,
    level_paths,
    load_level,
)


def test_map_size_and_initial_state(engine: GameEngine, level_01) -> None:
    assert engine.get_map_size() == 9
    assert engine.get_initially_revealed_region() == {5}
    assert engine.get_initially_revealed_assignments() == {5: True}
    assert engine.get_auxiliary_count() == level_01.get_auxiliary_count() == 0


def test_auxiliary_count_matches_level_with_extensions() -> None:
    for path in level_paths():
        level, _ = load_level(path.name)
        if level.get_auxiliary_count() > 0:
            engine = GameEngine(level)
            assert engine.get_auxiliary_count() == level.get_auxiliary_count()
            return

    pytest.fail("Không tìm thấy màn chơi có biến phụ để kiểm thử.")


def test_initial_formula_contains_units_and_revealed_clues(
    engine: GameEngine, level_01
) -> None:
    formula = engine.get_initial_formula()

    assert clause_counter(formula) == clause_counter(
        build_initial_formula(level_01)
    )
    assert is_sat(formula, 9)
    assert [5] in formula
    assert len(formula) > 1


def test_reveal_clue_returns_the_owner_clue(engine: GameEngine, level_01) -> None:
    for index in range(1, 10):
        assert engine.reveal_clue(index) is level_01.get_person(index).get_clue()


def test_validate_correct_criminal_verdict(engine: GameEngine, level_01) -> None:
    result, clue = engine.validate_verdict_and_provide_clue_if_correct(
        [[1]], 1, is_criminal_prediction=True
    )

    assert result == VerdictResult.CORRECT
    assert clue is level_01.get_person(1).get_clue()


def test_validate_correct_innocent_verdict(engine: GameEngine, level_01) -> None:
    result, clue = engine.validate_verdict_and_provide_clue_if_correct(
        [[-1]], 1, is_criminal_prediction=False
    )

    assert result == VerdictResult.CORRECT
    assert clue is level_01.get_person(1).get_clue()


def test_validate_contradicted_verdict(engine: GameEngine) -> None:
    result, clue = engine.validate_verdict_and_provide_clue_if_correct(
        [[1]], 1, is_criminal_prediction=False
    )

    assert result == VerdictResult.CONTRADICTED
    assert clue is None


def test_validate_contradicted_innocent_verdict(engine: GameEngine) -> None:
    result, clue = engine.validate_verdict_and_provide_clue_if_correct(
        [[-1]], 1, is_criminal_prediction=True
    )

    assert result == VerdictResult.CONTRADICTED
    assert clue is None


@pytest.mark.parametrize("is_criminal", [True, False])
def test_validate_not_provable_verdict(
    engine: GameEngine, is_criminal: bool
) -> None:
    result, clue = engine.validate_verdict_and_provide_clue_if_correct(
        [[1, 2]], 1, is_criminal_prediction=is_criminal
    )

    assert result == VerdictResult.NOT_PROVABLE
    assert clue is None


def test_validate_unknown_index_is_not_provable(engine: GameEngine) -> None:
    result, clue = engine.validate_verdict_and_provide_clue_if_correct(
        [[1]], 2, is_criminal_prediction=True
    )

    assert result == VerdictResult.NOT_PROVABLE
    assert clue is None


def test_validate_inconsistent_formula_raises(engine: GameEngine) -> None:
    with pytest.raises(ExceptionBrokenClues):
        engine.validate_verdict_and_provide_clue_if_correct(
            [[1], [-1]], 1, is_criminal_prediction=True
        )


def test_validate_does_not_mutate_formula(engine: GameEngine) -> None:
    formula = [[1, 2], [-1, 2]]

    engine.validate_verdict_and_provide_clue_if_correct(
        formula, 1, is_criminal_prediction=True
    )

    assert formula == [[1, 2], [-1, 2]]


def test_initial_region_getter_returns_copy(engine: GameEngine) -> None:
    region = engine.get_initially_revealed_region()
    region.add(1)

    assert engine.get_initially_revealed_region() == {5}


def test_initial_assignment_getter_returns_new_dict(engine: GameEngine) -> None:
    assignment = engine.get_initially_revealed_assignments()
    assignment[1] = True

    assert engine.get_initially_revealed_assignments() == {5: True}
