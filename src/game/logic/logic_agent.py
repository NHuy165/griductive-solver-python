from src.game.core.core_types import Assignment, Formula
from src.game.core.level import Level
from src.game.core.verdict_result import VerdictResult
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from src.game.logic.game_engine import GameEngine
from src.game.logic.sat_caller import SATCaller


class LogicAgent:
    @classmethod
    def classify_confirmed_people(cls, formula: Formula) -> Assignment:
        indices = cls._get_indices_in_formula(formula)
        if len(indices) == 0:
            return {}

        confirmed_literals, valid_assignment = (
            cls._SAT_solve_formula_for_literals_and_assignment(
                formula, map_size=max(indices)
            )
        )
        classified_people = cls._convert_literals_to_assignment(confirmed_literals)

        unconfirmed_indices = indices - set(classified_people)
        for index in sorted(unconfirmed_indices):
            is_criminal = SATCaller.SAT_call(
                formula,
                index,
                was_criminal_in_one_valid_assignment=valid_assignment[index],
            )

            if is_criminal is not None:
                classified_people[index] = is_criminal

        return classified_people

    @classmethod
    def get_hint(cls, formula: Formula, flipped: list[int]) -> int | None:
        indices = cls._get_indices_in_formula(formula)
        unflipped_indices = indices - set(flipped)
        if len(unflipped_indices) == 0:
            return None

        for index in cls.classify_confirmed_people(formula):
            if index in unflipped_indices:
                return index

        raise ValueError(
            "No more people can be classified from the current information."
        )

    @classmethod
    def solve_level(cls, engine: GameEngine) -> tuple[Assignment, list[Assignment]]:
        level = engine.level
        formula = cls._build_initial_formula(level)
        flipped = list(level.get_initially_revealed_region())
        flipped_people_per_step: list[Assignment] = []

        while len(flipped) < level.get_map_size():
            people_to_flip = cls._get_unflipped_confirmed_people(formula, flipped)

            if len(people_to_flip) == 0:
                raise ValueError(
                    "No further person can be confirmed with the current clues."
                )

            revealed_clauses = cls._flip_people_and_collect_clauses(
                engine, formula, people_to_flip
            )
            formula.extend(revealed_clauses)
            flipped.extend(people_to_flip)
            flipped_people_per_step.append(people_to_flip)

        complete_assignment = cls._get_complete_assignment(
            formula, level.get_map_size()
        )

        return complete_assignment, flipped_people_per_step

    @classmethod
    def _get_unflipped_confirmed_people(
        cls, formula: Formula, flipped: list[int]
    ) -> Assignment:
        confirmed_people = cls.classify_confirmed_people(formula)

        return {
            index: is_criminal
            for index, is_criminal in confirmed_people.items()
            if index not in flipped
        }

    @classmethod
    def _flip_people_and_collect_clauses(
        cls, engine: GameEngine, formula: Formula, people_to_flip: Assignment
    ) -> Formula:
        revealed_clauses: Formula = []

        for index, is_criminal in people_to_flip.items():
            verdict, clue = engine.validate_verdict_and_provide_clue_if_correct(
                formula, index, is_criminal
            )

            assert verdict == VerdictResult.CORRECT
            assert clue is not None

            revealed_clauses.extend(clue.to_cnf())

        return revealed_clauses

    @classmethod
    def _get_complete_assignment(cls, formula: Formula, map_size: int) -> Assignment:
        DPLL_SAT_solver = DpllSatSolver(map_size)

        is_SAT, _, valid_assignment = DPLL_SAT_solver.SAT_solve(formula)

        assert is_SAT
        assert valid_assignment is not None

        return valid_assignment

    @classmethod
    def _SAT_solve_formula_for_literals_and_assignment(
        cls, formula: Formula, map_size: int
    ) -> tuple[list[int], Assignment]:
        DPLL_SAT_solver = DpllSatSolver(map_size)

        is_SAT, confirmed_literals, valid_assignment = DPLL_SAT_solver.SAT_solve(
            formula
        )

        assert is_SAT is True
        assert confirmed_literals is not None
        assert valid_assignment is not None

        return confirmed_literals, valid_assignment

    @classmethod
    def _convert_literals_to_assignment(
        cls, confirmed_literals: list[int]
    ) -> Assignment:
        return {abs(literal): literal > 0 for literal in confirmed_literals}

    @classmethod
    def _build_initial_formula(cls, level: Level) -> Formula:
        formula: Formula = []

        for index in level.get_initially_revealed_region():
            formula.extend(level.get_person(index).get_clue().to_cnf())

        return formula

    @classmethod
    def _get_indices_in_formula(cls, formula: Formula) -> set[int]:
        return {abs(literal) for clause in formula for literal in clause}
