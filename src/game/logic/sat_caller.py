from src.game.core.core_types import Formula
from src.game.logic.DPLL_SAT_solver import DpllSatSolver


class SATCaller:
    @classmethod
    def SAT_call(
        cls,
        formula: Formula,
        index: int,
        was_criminal_in_one_possible_assignment: bool,
    ) -> bool | None:
        DPLL_SAT_solver = DpllSatSolver(0)

        opposite_literal = -index if was_criminal_in_one_possible_assignment else index
        formula_with_opposite = formula + [[opposite_literal]]

        is_SAT, _, _ = DPLL_SAT_solver.SAT_solve(formula_with_opposite)

        if is_SAT:
            return None

        return was_criminal_in_one_possible_assignment
