from src.game.core.core_types import Assignment, Formula


class DpllSatSolver:
    def __init__(self, map_size: int) -> None:
        self.map_size = map_size

    def SAT_solve(
        self, formula: Formula
    ) -> tuple[bool, list[int] | None, Assignment | None]:
        root_propagation = self._propagate_and_extract_implied_literals(formula)
        if root_propagation is None:
            return False, None, None
        root_formula, confirmed_literals = root_propagation

        decided_literals = self._solve(root_formula)
        if decided_literals is None:
            return False, None, None

        valid_literals = confirmed_literals + decided_literals
        valid_assignment = self._convert_literals_to_assignment(valid_literals)

        return True, confirmed_literals, valid_assignment

    def _propagate_and_extract_implied_literals(
        self, formula: Formula
    ) -> tuple[Formula, list[int]] | None:
        current_formula = formula
        propagated_literals: list[int] = []

        while True:
            if self._has_empty_clause(current_formula):
                return None

            unit_literal = self._find_first_instance_of_unit_clause_literal(
                current_formula
            )

            if unit_literal is None:
                return current_formula, propagated_literals

            current_formula = self._simplify_formula_using_literal(
                current_formula, unit_literal
            )
            propagated_literals.append(unit_literal)

    def _solve(self, formula: Formula) -> list[int] | None:
        if len(formula) == 0:
            return []

        index = self._select_min_index(formula)

        for guessed_literal in (index, -index):
            solution_literals = self._branch(formula, guessed_literal)

            if solution_literals is not None:
                return solution_literals

        return None

    def _branch(self, formula: Formula, guessed_literal: int) -> list[int] | None:
        formula_after_guess = self._simplify_formula_using_literal(
            formula, guessed_literal
        )
        propagation = self._propagate_and_extract_implied_literals(formula_after_guess)

        if propagation is None:
            return None

        remaining_formula, literals_implied_by_guess = propagation
        literals_satisfying_remaining_formula = self._solve(remaining_formula)

        if literals_satisfying_remaining_formula is None:
            return None

        return (
            [guessed_literal]
            + literals_implied_by_guess
            + literals_satisfying_remaining_formula
        )

    def _simplify_formula_using_literal(
        self, formula: Formula, literal: int
    ) -> Formula:
        simplified_formula: Formula = []

        for clause in formula:
            clause_already_satisfied = literal in clause
            if clause_already_satisfied:
                continue

            clause_without_wrong_literal = [
                other_literal for other_literal in clause if other_literal != -literal
            ]
            simplified_formula.append(clause_without_wrong_literal)

        return simplified_formula

    def _find_first_instance_of_unit_clause_literal(
        self, formula: Formula
    ) -> int | None:
        for clause in formula:
            if len(clause) == 1:
                return clause[0]

        return None

    def _has_empty_clause(self, formula: Formula) -> bool:
        return any(len(clause) == 0 for clause in formula)

    def _select_min_index(self, formula: Formula) -> int:
        return min(abs(literal) for clause in formula for literal in clause)

    def _convert_literals_to_assignment(self, valid_literals: list[int]) -> Assignment:
        valid_assignment = {index: False for index in range(1, self.map_size + 1)}

        for literal in valid_literals:
            valid_assignment[abs(literal)] = literal > 0

        return valid_assignment
