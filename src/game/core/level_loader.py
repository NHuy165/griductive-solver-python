import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.game.clue.clue import Clue
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
from src.game.core.core_types.exceptions import ExceptionInvalidLevel
from src.game.core.core_types.level_solve_result import LevelSolveStatus
from src.game.core.core_types.miscellaneous import Assignment, Formula
from src.game.core.level import Level
from src.game.core.person import Person
from src.game.logic.game_engine import GameEngine
from src.game.logic.logic_agent import LogicAgent

CLUE_BUILDERS: dict[ClueType, Callable[[dict[str, Any]], Clue]] = {
    ClueType.FACT: lambda c: FactClue(c["region"], c["is_criminal"]),
    ClueType.SAME: lambda c: SameClue(c["region"]),
    ClueType.DIFFERENT: lambda c: DifferentClue(c["region"]),
    ClueType.EXACTLY: lambda c: ExactlyClue(c["region"], c["k"]),
    ClueType.AT_LEAST: lambda c: AtLeastClue(c["region"], c["k"]),
    ClueType.AT_MOST: lambda c: AtMostClue(c["region"], c["k"]),
    ClueType.IMPLIES: lambda c: ImpliesClue(
        c["region"],
        c["is_criminal"],
        CLUE_BUILDERS[ClueType(c["conclusion"]["type"])](c["conclusion"]),
    ),
    ClueType.COMPARE: lambda c: CompareClue(
        c["region"], c["other_region"], c["equals"]
    ),
    ClueType.PARITY: lambda c: ParityClue(c["region"], c["is_odd"]),
}


class LevelLoader:
    @classmethod
    def load_level_from_file(cls, filepath: Path) -> tuple[Level, bool]:
        data = cls._load_data_from_file(filepath)
        level = cls._load_level_from_data(data)

        if not cls._validate_basic(level):
            raise ExceptionInvalidLevel("Invalid level data")

        solveable = cls._validate_solveable(level)

        return (level, solveable)

    @classmethod
    def _load_data_from_file(cls, filepath: Path) -> dict[str, Any]:
        with open(filepath, encoding="utf-8") as file:
            return json.load(file)

    @classmethod
    def _load_level_from_data(cls, data: dict[str, Any]) -> Level:
        size = data["size"]
        people = [cls._build_person(person_data) for person_data in data["people"]]
        cls._assign_auxiliary_indices(people, size**2)
        map_rows = [people[row * size : (row + 1) * size] for row in range(size)]

        return Level(map_rows, set(data["initially_revealed"]))

    @classmethod
    def _assign_auxiliary_indices(cls, people: list[Person], map_size: int) -> None:
        next_auxiliary_index = map_size + 1

        for person in people:
            clue = person.get_clue()
            clue.set_first_auxiliary_index(next_auxiliary_index)
            next_auxiliary_index += clue.get_auxiliary_count()

    @classmethod
    def _validate_basic(cls, level: Level) -> bool:
        return (
            cls._has_initially_revealed_region(level)
            and cls._revealed_region_in_range(level)
            and cls._names_are_unique_and_alphabetically_sorted(level)
            and cls._clues_point_to_existing_tiles(level)
            and cls._clues_hold_on_hidden_solution(level)
        )

    @classmethod
    def _validate_solveable(cls, level: Level) -> bool:
        formula = cls._build_full_clue_formula(level)
        agent = LogicAgent(GameEngine(level))

        # In a simulated solve, the final wave of clues are never fed back into the solver, therefore requiring a separate unique check with all the clues present.
        return agent.unique_check(formula) and cls._solver_finishes_level(agent, level)

    @classmethod
    def _build_person(cls, person_data: dict[str, Any]) -> Person:
        clue = cls._build_clue(person_data["clue"])

        return Person(
            person_data["name"],
            person_data["occupation"],
            clue,
            person_data["is_criminal"],
        )

    @classmethod
    def _build_clue(cls, clue_data: dict[str, Any]) -> Clue:
        return CLUE_BUILDERS[ClueType(clue_data["type"])](clue_data)

    @classmethod
    def _has_initially_revealed_region(cls, level: Level) -> bool:
        return len(level.get_initially_revealed_region()) > 0

    @classmethod
    def _revealed_region_in_range(cls, level: Level) -> bool:
        map_size = level.get_map_size()
        return all(
            0 < index <= map_size for index in level.get_initially_revealed_region()
        )

    @classmethod
    def _names_are_unique_and_alphabetically_sorted(cls, level: Level) -> bool:
        names = [level.get_person(i).get_name() for i in cls._all_indices(level)]
        unique = len(set(names)) == len(names)
        alphabetically_sorted = names == sorted(names)
        return unique and alphabetically_sorted

    @classmethod
    def _clues_point_to_existing_tiles(cls, level: Level) -> bool:
        map_size = level.get_map_size()
        return all(
            level.get_person(i).get_clue().is_valid_with_map(map_size)
            for i in cls._all_indices(level)
        )

    @classmethod
    def _clues_hold_on_hidden_solution(cls, level: Level) -> bool:
        solution = cls._get_hidden_solution(level)
        return all(
            level.get_person(i).get_clue().evaluate(solution)
            for i in cls._all_indices(level)
        )

    @classmethod
    def _build_full_clue_formula(cls, level: Level) -> Formula:
        formula: Formula = []
        for index in cls._all_indices(level):
            formula.extend(level.get_person(index).get_clue().to_cnf())
        formula.extend(cls._build_initial_unit_clauses(level))
        return formula

    @classmethod
    def _build_initial_unit_clauses(cls, level: Level) -> Formula:
        return [
            [index] if level.get_person(index).get_is_criminal() else [-index]
            for index in level.get_initially_revealed_region()
        ]

    @classmethod
    def _solver_finishes_level(cls, agent: LogicAgent, level: Level) -> bool:
        result = agent.solve_level()
        return (
            result.status == LevelSolveStatus.SUCCESS
            and result.final_assignment == cls._get_hidden_solution(level)
        )

    @classmethod
    def _all_indices(cls, level: Level) -> range:
        return range(1, level.get_map_size() + 1)

    @classmethod
    def _get_hidden_solution(cls, level: Level) -> Assignment:
        return {
            index: level.get_person(index).get_is_criminal()
            for index in cls._all_indices(level)
        }
