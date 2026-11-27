"""Kiểm thử tích hợp trên toàn bộ 30 màn chơi.

Mỗi màn phải có lời giải duy nhất, agent phải đi từ KB công khai ban đầu đến
đúng lời giải ẩn, và tại mỗi bước mọi phán quyết phải được suy ra chứ không
phải đoán.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.game.core.core_types.level_solve_result import LevelSolveStatus
from src.game.logic.game_engine import GameEngine
from src.game.logic.logic_agent import LogicAgent
from tests.helpers import (
    build_complete_knowledge_base,
    build_full_formula,
    build_initial_formula,
    clause_counter,
    hidden_solution,
    is_sat,
    level_paths,
    load_level,
    max_variable,
)

LEVEL_PATHS = level_paths()


@pytest.mark.parametrize("path", LEVEL_PATHS, ids=lambda path: path.stem)
def test_full_clue_set_is_satisfiable_and_unique(path: Path) -> None:
    level, _ = load_level(path.name)
    engine = GameEngine(level)
    agent = LogicAgent(engine)
    formula = build_full_formula(level)

    assert is_sat(formula, max_variable(formula))
    assert agent.unique_check(formula)


@pytest.mark.parametrize("path", LEVEL_PATHS, ids=lambda path: path.stem)
def test_initial_public_knowledge_base_is_consistent(path: Path) -> None:
    level, _ = load_level(path.name)
    engine = GameEngine(level)
    formula = engine.get_initial_formula()
    initial_indices = engine.get_initially_revealed_region()

    assert formula
    assert is_sat(formula, max_variable(formula))
    assert clause_counter(formula) == clause_counter(
        build_initial_formula(level)
    )

    for index in initial_indices:
        person = level.get_person(index)
        unit = [index] if person.get_is_criminal() else [-index]
        assert unit in formula
        assert all(
            clause in formula for clause in person.get_clue().to_cnf()
        )


@pytest.mark.parametrize("path", LEVEL_PATHS, ids=lambda path: path.stem)
def test_agent_reaches_hidden_solution_without_guessing(path: Path) -> None:
    level, _ = load_level(path.name)
    engine = GameEngine(level)
    agent = LogicAgent(engine)
    hidden = hidden_solution(level)
    map_size = level.get_map_size()

    result = agent.solve_level()

    assert result.status == LevelSolveStatus.SUCCESS
    assert result.final_assignment == hidden
    assert len(result.solve_steps) >= 1
    assert sum(
        len(step.assignment_result.confirmed_assignments)
        for step in result.solve_steps
    ) == map_size - len(engine.get_initially_revealed_region())

    previous_formula = engine.get_initial_formula()
    previous_flipped = engine.get_initially_revealed_region()
    max_var = max(map_size, max_variable(previous_formula))

    for step_index, step in enumerate(result.solve_steps):
        assert clause_counter(step.current_formula) == clause_counter(
            previous_formula
        )
        assert step.current_indices_flipped == previous_flipped
        assert is_sat(step.current_formula, max_var)

        confirmed = step.assignment_result.confirmed_assignments
        assert confirmed
        assert len(step.revealed_clues) == len(confirmed)

        for index, is_criminal in confirmed.items():
            assert index not in previous_flipped
            assert is_criminal is hidden[index]
            opposite = -index if is_criminal else index
            assert not is_sat(step.current_formula + [[opposite]], max_var)

        expected_formula = list(previous_formula)
        for index, is_criminal in confirmed.items():
            expected_formula.append([index] if is_criminal else [-index])

        for (index, _), clue in zip(confirmed.items(), step.revealed_clues):
            assert clue is level.get_person(index).get_clue()
            assert clue.evaluate(hidden)
            expected_formula.extend(clue.to_cnf())

        if step_index + 1 < len(result.solve_steps):
            assert clause_counter(
                result.solve_steps[step_index + 1].current_formula
            ) == clause_counter(expected_formula)

        previous_formula = expected_formula
        previous_flipped = previous_flipped | set(confirmed)

    assert previous_flipped == set(range(1, map_size + 1))
    assert clause_counter(previous_formula) == clause_counter(
        build_complete_knowledge_base(level)
    )


@pytest.mark.parametrize("path", LEVEL_PATHS, ids=lambda path: path.stem)
def test_every_clue_is_true_on_the_hidden_solution(path: Path) -> None:
    level, _ = load_level(path.name)
    hidden = hidden_solution(level)

    for index in range(1, level.get_map_size() + 1):
        clue = level.get_person(index).get_clue()
        assert clue.evaluate(hidden)


@pytest.mark.parametrize("path", LEVEL_PATHS, ids=lambda path: path.stem)
def test_agent_never_uses_a_guessed_verdict(path: Path) -> None:
    level, _ = load_level(path.name)
    engine = GameEngine(level)
    agent = LogicAgent(engine)
    result = agent.solve_level()
    max_var = max(
        level.get_map_size(),
        max_variable(build_full_formula(level)),
    )

    for step in result.solve_steps:
        for index, is_criminal in step.assignment_result.confirmed_assignments.items():
            opposite = -index if is_criminal else index
            assert not is_sat(step.current_formula + [[opposite]], max_var)
