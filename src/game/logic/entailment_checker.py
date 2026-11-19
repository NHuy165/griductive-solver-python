from src.game.core.core_types.entailment_check_result import (
    EntailmentCheckResult,
    EntailmentCheckStatus,
)
from src.game.core.core_types.miscellaneous import Formula
from src.game.logic.DPLL_SAT_solver import DpllSatSolver


class EntailmentChecker:
    @classmethod
    def entailment_check(
        cls,
        formula: Formula,
        index: int,
        was_criminal_in_one_possible_assignment: bool,
    ) -> EntailmentCheckResult:
        # Assumes the base formula is consistent

        formula_with_opposite = cls._add_opposite_literal_to_formula(
            formula, index, was_criminal_in_one_possible_assignment
        )

        entailment_check_result = cls._classify_index_using_SAT_solve(
            formula_with_opposite, was_criminal_in_one_possible_assignment
        )

        return entailment_check_result

    @classmethod
    def _add_opposite_literal_to_formula(
        cls,
        formula: Formula,
        index: int,
        was_criminal_in_one_possible_assignment: bool,
    ) -> Formula:

        opposite_literal = -index if was_criminal_in_one_possible_assignment else index
        formula_with_opposite = formula + [[opposite_literal]]

        return formula_with_opposite

    @classmethod
    def _classify_index_using_SAT_solve(
        cls,
        formula_with_opposite: Formula,
        was_criminal_in_one_possible_assignment: bool,
    ) -> EntailmentCheckResult:
        DPLL_SAT_solver = DpllSatSolver(0)

        SAT_result = DPLL_SAT_solver.SAT_solve(formula_with_opposite)

        if SAT_result.is_SAT:
            return EntailmentCheckResult(
                EntailmentCheckStatus.UNKNOWN, SAT_result.events
            )

        status = (
            EntailmentCheckStatus.CRIMINAL
            if was_criminal_in_one_possible_assignment
            else EntailmentCheckStatus.INNOCENT
        )

        return EntailmentCheckResult(status, SAT_result.events)
