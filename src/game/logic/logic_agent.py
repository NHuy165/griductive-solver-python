from dataclasses import dataclass
from time import perf_counter

from src.game.clue.clue import Clue
from src.game.core.core_types.assignment_result import AssignmentResult
from src.game.core.core_types.entailment_check_result import (
    EntailmentCheckStatus,
)
from src.game.core.core_types.exceptions import ExceptionBrokenClues
from src.game.core.core_types.level_solve_result import (
    LevelSolveResult,
    LevelSolveStatus,
    LevelSolveStepResult,
)
from src.game.core.core_types.miscellaneous import Assignment, Clause, Formula
from src.game.core.core_types.SAT_solve_result import SATSolveEvents, SATSolveResult
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from src.game.logic.entailment_checker import EntailmentChecker
from src.game.logic.game_engine import GameEngine


@dataclass
class LevelSolveState:
    formula: Formula
    flipped: set[int]
    assignment: Assignment
    steps: list[LevelSolveStepResult]


class LogicAgent:
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine

    def assign_from_formula_with_time(
        self, formula: Formula
    ) -> tuple[AssignmentResult, float]:
        start = perf_counter()

        assignment_result = self.assign_from_formula(formula)

        end = perf_counter()

        return assignment_result, end - start

    def assign_from_formula(self, formula: Formula) -> AssignmentResult:
        non_auxiliary_indices_in_formula = self._get_non_auxiliary_indices_in_formula(
            formula
        )
        assert len(non_auxiliary_indices_in_formula) > 0
        SAT_solve_result = self._SAT_solve_formula(
            formula, max_index=self._get_max_index(formula)
        )

        assert SAT_solve_result.confirmed_literals is not None
        confirmed_non_auxiliary_literals = [
            literal
            for literal in SAT_solve_result.confirmed_literals
            if not self._is_auxiliary_literal(literal)
        ]
        confirmed_assignments = self._convert_literals_to_assignment(
            confirmed_non_auxiliary_literals
        )

        assignments_confirmed_with_entailment_checks, events_in_entailment_checks = (
            self._use_entailment_checks_to_probe(
                formula=formula,
                non_auxiliary_indices_in_formula=non_auxiliary_indices_in_formula,
                confirmed_indices=set(confirmed_assignments),
                SAT_solve_result=SAT_solve_result,
            )
        )

        confirmed_assignments.update(assignments_confirmed_with_entailment_checks)

        return self._build_assignment_result(
            non_auxiliary_indices_in_formula=non_auxiliary_indices_in_formula,
            SAT_solve_result=SAT_solve_result,
            non_auxiliary_literals_confirmed_by_propagation=confirmed_non_auxiliary_literals,
            events_in_entailment_checks=events_in_entailment_checks,
            confirmed_assignments=confirmed_assignments,
        )

    def get_hint(self, formula: Formula, flipped: set[int]) -> int:
        assert len(flipped) < self.engine.get_map_size()

        indices = self._get_non_auxiliary_indices_in_formula(formula)
        unflipped_indices = indices - set(flipped)
        if len(unflipped_indices) == 0:
            raise ExceptionBrokenClues(
                "No more people can be classified from the current information."
            )

        assignment_result = self.assign_from_formula(formula)
        for index in assignment_result.confirmed_assignments:
            if index in unflipped_indices:
                return index

        raise ExceptionBrokenClues(
            "No more people can be classified from the current information."
        )

    def solve_level_with_time(self) -> tuple[LevelSolveResult, float]:
        start = perf_counter()

        solve_result = self.solve_level()

        end = perf_counter()

        return solve_result, end - start

    def solve_level(self) -> LevelSolveResult:
        state = self._initiate_solve_state()

        while len(state.flipped) < self.engine.get_map_size():
            status = self._solve_step(state)

            if status is not None:
                return LevelSolveResult(
                    status=status,
                    final_assignment=state.assignment,
                    solve_steps=state.steps,
                )

        return LevelSolveResult(
            LevelSolveStatus.SUCCESS,
            final_assignment=state.assignment,
            solve_steps=state.steps,
        )

    def unique_check(self, formula: Formula) -> bool:
        DPLL_SAT_solver = DpllSatSolver(
            max(self.engine.get_map_size(), self._get_max_index(formula))
        )
        SAT_solve_result = DPLL_SAT_solver.SAT_solve(formula)

        if not SAT_solve_result.is_SAT:
            return False

        possible_assignment = SAT_solve_result.possible_assignment
        assert possible_assignment is not None

        person_assignment = {
            index: value
            for index, value in possible_assignment.items()
            if not self._is_auxiliary_literal(index)
        }
        assert len(person_assignment) == self.engine.get_map_size()

        counter_clause: Clause = [
            -index if value else index for index, value in person_assignment.items()
        ]
        extended_formula = formula + [counter_clause]

        SAT_solve_result = DPLL_SAT_solver.SAT_solve(extended_formula)
        is_unique = not SAT_solve_result.is_SAT

        return is_unique

    def _initiate_solve_state(self) -> LevelSolveState:
        formula = self.engine.get_initial_formula()
        flipped = self.engine.get_initially_revealed_region()
        assignment = self.engine.get_initially_revealed_assignments()
        steps: list[LevelSolveStepResult] = []

        return LevelSolveState(formula, flipped, assignment, steps)

    def _build_assignment_result(
        self,
        non_auxiliary_indices_in_formula: set[int],
        SAT_solve_result: SATSolveResult,
        non_auxiliary_literals_confirmed_by_propagation: list[int],
        events_in_entailment_checks: dict[int, SATSolveEvents],
        confirmed_assignments: Assignment,
    ) -> AssignmentResult:
        assert SAT_solve_result.confirmed_literals is not None

        non_auxiliary_indices_confirmed_by_propagation = sorted(
            [
                abs(literal)
                for literal in non_auxiliary_literals_confirmed_by_propagation
            ]
        )
        non_auxiliary_indices_confirmed_by_entailment_checks = sorted(
            set(confirmed_assignments)
            - set(non_auxiliary_indices_confirmed_by_propagation)
        )
        non_auxiliary_indices_unknown_by_entailment_checks = sorted(
            non_auxiliary_indices_in_formula - set(confirmed_assignments)
        )
        events_to_reach_possible_assignment = SAT_solve_result.events

        assert SAT_solve_result.events is not None
        return AssignmentResult(
            non_auxiliary_indices_confirmed_by_propagation,
            non_auxiliary_indices_confirmed_by_entailment_checks,
            non_auxiliary_indices_unknown_by_entailment_checks,
            events_to_reach_possible_assignment,
            events_in_entailment_checks,
            confirmed_assignments,
        )

    def _solve_step(self, state: LevelSolveState) -> LevelSolveStatus | None:
        try:
            full_assignment_result = self.assign_from_formula(state.formula)
        except ExceptionBrokenClues:
            return LevelSolveStatus.INCONSISTENT

        step_assignment_result = self._remove_flipped_from_assignment_result(
            full_assignment_result, state.flipped
        )

        if len(step_assignment_result.confirmed_assignments) == 0:
            return LevelSolveStatus.STUCK

        self._update_state(state, step_assignment_result)

        return None

    def _update_state(
        self, state: LevelSolveState, step_assignment_result: AssignmentResult
    ) -> None:
        unflipped_confirmed_assignments = step_assignment_result.confirmed_assignments
        revealed_clues = self._reveal_confirmed_clues(
            list(unflipped_confirmed_assignments.keys())
        )

        level_solve_step = LevelSolveStepResult(
            current_formula=list(state.formula),
            current_indices_flipped=state.flipped.copy(),
            assignment_result=step_assignment_result,
            revealed_clues=revealed_clues,
        )
        state.steps.append(level_solve_step)
        state.formula.extend(self._build_formula_from_clues(revealed_clues))
        state.formula.extend(
            [
                [index] if is_criminal else [-index]
                for index, is_criminal in unflipped_confirmed_assignments.items()
            ]
        )
        state.flipped.update(unflipped_confirmed_assignments)
        state.assignment.update(unflipped_confirmed_assignments)

    def _remove_flipped_from_assignment_result(
        self, assignment_result: AssignmentResult, flipped: set[int]
    ) -> AssignmentResult:
        indices_confirmed_by_propagation = sorted(
            set(assignment_result.non_auxiliary_indices_confirmed_by_propagation)
            - flipped
        )
        indices_confirmed_by_entailment_checks = sorted(
            assignment_result.non_auxiliary_indices_confirmed_by_entailment_checks
        )
        indices_unknown_by_entailment_checks = sorted(
            assignment_result.non_auxiliary_indices_unknown_by_entailment_checks
        )
        assignment = self._remove_flipped_from_confirmed_assignments(
            assignment_result.confirmed_assignments, flipped
        )
        return AssignmentResult(
            indices_confirmed_by_propagation,
            indices_confirmed_by_entailment_checks,
            indices_unknown_by_entailment_checks,
            assignment_result.events_to_reach_possible_assignment,
            assignment_result.events_in_entailment_checks,
            assignment,
        )

    def _use_entailment_checks_to_probe(
        self,
        formula: Formula,
        non_auxiliary_indices_in_formula: set[int],
        confirmed_indices: set[int],
        SAT_solve_result: SATSolveResult,
    ) -> tuple[Assignment, dict[int, SATSolveEvents]]:
        classified_people: Assignment = {}
        assert SAT_solve_result.possible_assignment is not None
        indices_to_probe = (
            set(SAT_solve_result.possible_assignment).intersection(
                non_auxiliary_indices_in_formula
            )
            - confirmed_indices
        )
        probe_events: dict[int, SATSolveEvents] = {}

        for index in sorted(indices_to_probe):
            entailment_check_result = EntailmentChecker.entailment_check(
                formula,
                index,
                was_criminal_in_one_possible_assignment=SAT_solve_result.possible_assignment[
                    index
                ],
            )

            if entailment_check_result.status != EntailmentCheckStatus.UNKNOWN:
                classified_people[index] = (
                    entailment_check_result.status == EntailmentCheckStatus.CRIMINAL
                )
            probe_events[index] = entailment_check_result.events
        assert len(probe_events) == len(indices_to_probe)

        return classified_people, probe_events

    def _remove_flipped_from_confirmed_assignments(
        self, confirmed_assignments: Assignment, flipped: set[int]
    ) -> Assignment:
        unflipped_confirmed_assignments = {
            index: is_criminal
            for index, is_criminal in confirmed_assignments.items()
            if index not in flipped
        }

        return unflipped_confirmed_assignments

    def _reveal_confirmed_clues(
        self,
        unflipped_confirmed_indices: list[int],
    ) -> list[Clue]:
        revealed_clues: list[Clue] = []

        for index in unflipped_confirmed_indices:
            clue = self.engine.reveal_clue(index)

            assert clue is not None
            revealed_clues.append(clue)

        return revealed_clues

    def _SAT_solve_formula(self, formula: Formula, max_index: int) -> SATSolveResult:
        DPLL_SAT_solver = DpllSatSolver(max_index)

        SAT_result = DPLL_SAT_solver.SAT_solve(formula)

        if not SAT_result.is_SAT:
            raise ExceptionBrokenClues("Clues are inconsistent.")

        assert SAT_result.possible_assignment is not None

        return SAT_result

    def _convert_literals_to_assignment(
        self, confirmed_non_auxiliary_literals: list[int]
    ) -> Assignment:
        return {
            abs(literal): literal > 0 for literal in confirmed_non_auxiliary_literals
        }

    def _build_formula_from_clues(self, clues: list[Clue]) -> Formula:
        formula: Formula = []

        for clue in clues:
            formula.extend(clue.to_cnf())

        return formula

    def _get_non_auxiliary_indices_in_formula(self, formula: Formula) -> set[int]:
        return {
            abs(literal)
            for clause in formula
            for literal in clause
            if not self._is_auxiliary_literal(literal)
        }

    def _get_max_index(self, formula: Formula) -> int:
        return max(abs(literal) for clause in formula for literal in clause)

    def _is_auxiliary_literal(self, literal: int) -> bool:
        return abs(literal) > self.engine.get_map_size()
