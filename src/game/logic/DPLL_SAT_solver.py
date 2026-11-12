from time import perf_counter

from src.game.core.core_types import Assignment, Clause, Formula
from src.game.core.SAT_solve_result import SATSolveEvent, SATSolveEvents, SATSolveResult


class DpllSatSolver:
    def __init__(self, map_size: int) -> None:
        self.map_size = map_size

    def SAT_solve_with_time(self, formula) -> tuple[SATSolveResult, float]:
        start = perf_counter()

        SAT_result = self.SAT_solve(formula)

        end = perf_counter()

        return (SAT_result, end - start)

    def SAT_solve(self, formula: Formula) -> SATSolveResult:
        events: SATSolveEvents = []

        root_propagation = self._propagate_and_extract_implied_literals(formula)
        if root_propagation is None:
            return SATSolveResult(False, None, None, None)
        propagated_formula, confirmed_literals, propagated_events = root_propagation

        events.extend(propagated_events)

        solve_result = self._solve(propagated_formula)
        if solve_result is None:
            return SATSolveResult(False, None, None, None)
        decided_literals, solve_events = solve_result

        events.extend(solve_events)

        valid_literals = confirmed_literals + decided_literals
        possible_assignment = self._convert_literals_to_assignment_if_needed(
            valid_literals
        )

        return SATSolveResult(
            is_SAT=True,
            confirmed_literals=valid_literals,
            possible_assignment=possible_assignment,
            events=events,
        )

    def _propagate_and_extract_implied_literals(
        self, formula: Formula
    ) -> tuple[Formula, list[int], SATSolveEvents] | None:
        current_formula = formula
        propagated_literals: list[int] = []

        while True:
            if self._contains_insoluble_clause(current_formula):
                return None

            literal = self._find_first_instance_of_unit_clause(current_formula)

            if literal is None:
                propagation_events: SATSolveEvents = [
                    (SATSolveEvent.PROPAGATION, propagated_literal)
                    for propagated_literal in propagated_literals
                ]
                return current_formula, propagated_literals, propagation_events

            propagated_literals.append(literal)

            current_formula = self._simplify_formula_using_literal(
                current_formula, literal
            )

    def _solve(self, formula: Formula) -> tuple[list[int], SATSolveEvents] | None:
        if len(formula) == 0:
            return [], []
        events: SATSolveEvents = []

        index = self._select_min_index(formula)

        for guessed_literal in (index, -index):
            events.append((SATSolveEvent.DECISION, guessed_literal))
            solution_literals_and_events = self._branch(formula, guessed_literal)

            if solution_literals_and_events is not None:
                solution_literals, solution_events = solution_literals_and_events
                events.extend(solution_events)
                return solution_literals, events

            events.append((SATSolveEvent.BACKTRACK, guessed_literal))

        return None

    def _branch(
        self, formula: Formula, guessed_literal: int
    ) -> tuple[list[int], SATSolveEvents] | None:
        formula_after_guess = self._simplify_formula_using_literal(
            formula, guessed_literal
        )
        events: SATSolveEvents = []
        propagation = self._propagate_and_extract_implied_literals(formula_after_guess)

        if propagation is None:
            return None

        remaining_formula, literals_implied_by_guess, propagation_events = propagation
        events.extend(propagation_events)
        solve_result = self._solve(remaining_formula)

        if solve_result is None:
            return None

        literals_satisfying_remaining_formula, solve_events = solve_result
        events.extend(solve_events)

        return (
            [guessed_literal]
            + literals_implied_by_guess
            + literals_satisfying_remaining_formula,
            events,
        )

    def _simplify_formula_using_literal(
        self, formula: Formula, literal: int
    ) -> Formula:
        simplified_formula: Formula = []

        for clause in formula:
            simplified_clause = self._simplify_clause_using_literal(clause, literal)

            if simplified_clause is None:
                continue

            simplified_formula.append(simplified_clause)

        return simplified_formula

    def _simplify_clause_using_literal(
        self, clause: Clause, literal: int
    ) -> Clause | None:
        clause_already_satisfied = literal in clause
        if clause_already_satisfied:
            return None

        clause_without_wrong_literal = [
            other_literal for other_literal in clause if other_literal != -literal
        ]
        return clause_without_wrong_literal

    def _find_first_instance_of_unit_clause(self, formula: Formula) -> int | None:
        for clause in formula:
            if len(clause) == 1:
                return clause[0]

        return None

    def _contains_insoluble_clause(self, formula: Formula) -> bool:
        return any(len(clause) == 0 for clause in formula)

    def _select_min_index(self, formula: Formula) -> int:
        return min(abs(literal) for clause in formula for literal in clause)

    def _convert_literals_to_assignment_if_needed(
        self, valid_literals: list[int]
    ) -> Assignment:
        assignment_not_needed = self.map_size == 0

        if assignment_not_needed:
            possible_assignment = {}
        else:
            possible_assignment = {
                index: False for index in range(1, self.map_size + 1)
            }

            for literal in valid_literals:
                possible_assignment[abs(literal)] = literal > 0

        return possible_assignment
