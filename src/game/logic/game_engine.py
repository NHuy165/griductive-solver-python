from src.game.clue.clue import Clue
from src.game.core.core_types.entailment_check_result import (
    EntailmentCheckStatus,
)
from src.game.core.core_types.exceptions import ExceptionBrokenClues
from src.game.core.core_types.miscellaneous import Assignment, Formula
from src.game.core.core_types.verdict_result import VerdictResult
from src.game.core.level import Level
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from src.game.logic.entailment_checker import EntailmentChecker


class GameEngine:
    def __init__(self, level: Level) -> None:
        self.level = level

    def get_map_size(self) -> int:
        return self.level.get_map_size()

    def get_initially_revealed_region(self) -> set[int]:
        return self.level.get_initially_revealed_region().copy()

    def get_initially_revealed_assignments(self) -> Assignment:
        assignment: Assignment = {
            index: self.level.get_person(index).get_is_criminal()
            for index in self.level.get_initially_revealed_region()
        }
        return assignment

    def get_initial_formula(self) -> Formula:
        formula: Formula = []

        for index in self.get_initially_revealed_region():
            person = self.level.get_person(index)
            formula.append([index if person.get_is_criminal() else -index])
            formula.extend(person.get_clue().to_cnf())

        return formula

    def reveal_clue(self, index: int) -> Clue:
        return self.level.get_person(index).get_clue()

    def validate_verdict_and_provide_clue_if_correct(
        self, formula: Formula, index: int, is_criminal_prediction: bool
    ) -> tuple[VerdictResult, Clue | None]:
        index_was_assigned_criminal = self._get_possible_index_assignment(
            formula, index
        )
        # Assumes the formula is consistent, throws an error if not.
        if index_was_assigned_criminal is None:
            raise ExceptionBrokenClues("Clues are inconsistent.")

        entailment_check_status = EntailmentChecker.entailment_check(
            formula,
            index,
            was_criminal_in_one_possible_assignment=index_was_assigned_criminal,
        ).status

        if entailment_check_status == EntailmentCheckStatus.UNKNOWN:
            return VerdictResult.NOT_PROVABLE, None

        expected = (
            EntailmentCheckStatus.CRIMINAL
            if is_criminal_prediction
            else EntailmentCheckStatus.INNOCENT
        )
        if entailment_check_status == expected:
            return VerdictResult.CORRECT, self.level.get_person(index).get_clue()
        return VerdictResult.CONTRADICTED, None

    def _get_possible_index_assignment(
        self, formula: Formula, index: int
    ) -> bool | None:
        DPLL_SAT_solver = DpllSatSolver(self.level.get_map_size())

        SAT_result = DPLL_SAT_solver.SAT_solve(formula)

        if not SAT_result.is_SAT:
            return None

        assert SAT_result.possible_assignment is not None
        index_was_assigned_criminal = SAT_result.possible_assignment[index]

        return index_was_assigned_criminal
