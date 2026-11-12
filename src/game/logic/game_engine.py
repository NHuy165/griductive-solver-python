from src.game.clue.clue import Clue
from src.game.core.core_types import Formula
from src.game.core.level import Level
from src.game.core.verdict_result import VerdictResult
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from src.game.logic.sat_caller import SATCaller


class GameEngine:
    def __init__(self, level: Level) -> None:
        self.level = level

    def validate_verdict_and_provide_clue_if_correct(
        self, formula: Formula, index: int, is_criminal_prediction: bool
    ) -> tuple[VerdictResult, Clue | None]:
        index_was_assigned_criminal = self._get_possible_index_assignment(
            formula, index
        )
        is_criminal = SATCaller.SAT_call(
            formula,
            index,
            was_criminal_in_one_possible_assignment=index_was_assigned_criminal,
        )

        if is_criminal is None:
            return VerdictResult.NOT_PROVABLE, None

        if is_criminal != is_criminal_prediction:
            return VerdictResult.CONTRADICTED, None

        return VerdictResult.CORRECT, self.level.get_person(index).get_clue()

    def _get_possible_index_assignment(self, formula: Formula, index: int) -> bool:
        DPLL_SAT_solver = DpllSatSolver(self.level.get_map_size())

        SAT_result = DPLL_SAT_solver.SAT_solve(formula)
        assert SAT_result.is_SAT is True
        assert SAT_result.possible_assignment is not None

        index_was_assigned_criminal = SAT_result.possible_assignment[index]

        return index_was_assigned_criminal
