from src.game.core.core_types import Assignment, Formula
from src.game.core.level import Level
from src.game.core.verdict_result import VerdictResult
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from src.game.logic.game_engine import GameEngine
from src.game.logic.sat_caller import SATCaller


class LogicAgent:
    def __init__(self, level: Level) -> None:
        self.level = level

    def classify_confirmed_people(self, formula: Formula) -> Assignment:
        indices = self._get_indices_in_formula(formula)
        assert len(indices) > 0
        map_size = max(indices)

        confirmed_literals, possible_assignment = (
            self._SAT_solve_formula_for_literals_and_assignment(formula, map_size)
        )
        classified_indices = self._convert_literals_to_assignment(confirmed_literals)

        unconfirmed_indices = indices - set(classified_indices)
        indices_classified_with_SAT_calls = self._use_SAT_calls_to_classify_indices(
            indices=sorted(unconfirmed_indices),
            formula=formula,
            possible_assignment=possible_assignment,
        )

        classified_indices.update(indices_classified_with_SAT_calls)

        return classified_indices

    def get_hint(self, formula: Formula, flipped: list[int]) -> int | None:
        assert len(flipped) < self.level.get_map_size()

        indices = self._get_indices_in_formula(formula)
        unflipped_indices = indices - set(flipped)
        if len(unflipped_indices) == 0:
            raise ValueError(
                "No more people can be classified from the current information."
            )

        for index in self.classify_confirmed_people(formula):
            if index in unflipped_indices:
                return index

        raise ValueError(
            "No more people can be classified from the current information."
        )

    def solve_level(self) -> tuple[Assignment, list[Assignment]]:
        engine = GameEngine(self.level)
        formula = self._build_initial_formula(self.level)
        flipped = list(self.level.get_initially_revealed_region())
        flipped_at_each_step: list[Assignment] = []

        while len(flipped) < self.level.get_map_size():
            unflipped_confirmed_indices = self._get_unflipped_confirmed_indices(
                formula, flipped
            )

            if len(unflipped_confirmed_indices) == 0:
                raise ValueError(
                    "No further person can be confirmed with the current clues."
                )

            revealed_clauses = self._flip_people_and_collect_clauses(
                engine, formula, unflipped_confirmed_indices
            )

            formula.extend(revealed_clauses)
            flipped.extend(unflipped_confirmed_indices)
            flipped_at_each_step.append(unflipped_confirmed_indices)

        complete_assignment = self._get_complete_assignment(
            formula, self.level.get_map_size()
        )

        return complete_assignment, flipped_at_each_step

    def _use_SAT_calls_to_classify_indices(
        self,
        indices: list[int],
        formula: Formula,
        possible_assignment: Assignment,
    ) -> Assignment:
        classified_people: Assignment = {}

        for index in sorted(indices):
            is_criminal = SATCaller.SAT_call(
                formula,
                index,
                was_criminal_in_one_possible_assignment=possible_assignment[index],
            )

            if is_criminal is not None:
                classified_people[index] = is_criminal

        return classified_people

    def _get_unflipped_confirmed_indices(
        self, formula: Formula, flipped: list[int]
    ) -> Assignment:
        confirmed_people = self.classify_confirmed_people(formula)

        return {
            index: is_criminal
            for index, is_criminal in confirmed_people.items()
            if index not in flipped
        }

    def _flip_people_and_collect_clauses(
        self,
        engine: GameEngine,
        formula: Formula,
        unflipped_confirmed_indices: Assignment,
    ) -> Formula:
        revealed_clauses: Formula = []

        for index, is_criminal in unflipped_confirmed_indices.items():
            verdict, clue = engine.validate_verdict_and_provide_clue_if_correct(
                formula, index, is_criminal
            )

            assert verdict == VerdictResult.CORRECT
            assert clue is not None

            revealed_clauses.extend(clue.to_cnf())

        return revealed_clauses

    def _get_complete_assignment(self, formula: Formula, map_size: int) -> Assignment:
        DPLL_SAT_solver = DpllSatSolver(map_size)

        is_SAT, _, possible_assignment = DPLL_SAT_solver.SAT_solve(formula)

        assert is_SAT
        assert possible_assignment is not None

        return possible_assignment

    def _SAT_solve_formula_for_literals_and_assignment(
        self, formula: Formula, map_size: int
    ) -> tuple[list[int], Assignment]:
        DPLL_SAT_solver = DpllSatSolver(map_size)

        is_SAT, confirmed_literals, possible_assignment = DPLL_SAT_solver.SAT_solve(
            formula
        )

        assert is_SAT is True
        assert confirmed_literals is not None
        assert possible_assignment is not None

        return confirmed_literals, possible_assignment

    def _convert_literals_to_assignment(
        self, confirmed_literals: list[int]
    ) -> Assignment:
        return {abs(literal): literal > 0 for literal in confirmed_literals}

    def _build_initial_formula(self, level: Level) -> Formula:
        formula: Formula = []

        for index in level.get_initially_revealed_region():
            formula.extend(level.get_person(index).get_clue().to_cnf())

        return formula

    def _get_indices_in_formula(self, formula: Formula) -> set[int]:
        return {abs(literal) for clause in formula for literal in clause}
