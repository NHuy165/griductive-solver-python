from copy import deepcopy
from time import perf_counter

from src.game.clue.clue import Clue
from src.game.core.core_types.assignment_result import AssignmentResult
from src.game.core.core_types.exceptions import ExceptionBrokenClues
from src.game.core.core_types.level_solve_result import (
    LevelSolveResult,
    LevelSolveStatus,
    LevelSolveStepResult,
)
from src.game.core.core_types.miscellaneous import Assignment, Clause, Formula
from src.game.core.core_types.SAT_call_result import SATCallResult
from src.game.core.core_types.SAT_solve_result import SATSolveResult
from src.game.core.core_types.verdict_result import VerdictResult
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from src.game.logic.game_engine import GameEngine
from src.game.logic.sat_caller import SATCaller


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
        indices = self._get_indices_in_formula(formula)
        assert len(indices) > 0
        map_size = max(indices)

        SAT_solve_result = self._SAT_solve_formula(formula, map_size)
        assert SAT_solve_result.confirmed_literals is not None
        classified_indices = self._convert_literals_to_assignment(
            SAT_solve_result.confirmed_literals
        )

        unconfirmed_indices = indices - set(classified_indices)
        assert SAT_solve_result.possible_assignment is not None

        indices_classified_with_SAT_calls = self._use_SAT_calls_to_assign_indices(
            indices=sorted(unconfirmed_indices),
            formula=formula,
            possible_assignment=SAT_solve_result.possible_assignment,
        )

        classified_indices.update(indices_classified_with_SAT_calls)

        indices_confirmed_by_propagation = sorted(
            [abs(literal) for literal in SAT_solve_result.confirmed_literals]
        )
        indices_confirmed_by_SAT_calls = sorted(
            set(classified_indices.keys()) - set(indices_confirmed_by_propagation)
        )
        indices_unknown_by_SAT_calls = sorted(
            unconfirmed_indices - set(indices_classified_with_SAT_calls)
        )

        assert SAT_solve_result.events is not None
        return AssignmentResult(
            indices_confirmed_by_propagation=indices_confirmed_by_propagation,
            indices_confirmed_by_SAT_calls=indices_confirmed_by_SAT_calls,
            indices_unknown_by_SAT_calls=indices_unknown_by_SAT_calls,
            events_to_reach_possible_assignment=SAT_solve_result.events,
            confirmed_assignments=classified_indices,
        )

    def get_hint(self, formula: Formula, flipped: set[int]) -> int:
        assert len(flipped) < self.engine.get_map_size()

        indices = self._get_indices_in_formula(formula)
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
        formula = self.engine.get_initial_formula()
        flipped = self.engine.get_initially_revealed_region()
        final_assignment: Assignment = self.engine.get_initially_revealed_assignments()
        solve_steps: list[LevelSolveStepResult] = []

        if len(flipped) == self.engine.get_map_size():
            return LevelSolveResult(
                status=LevelSolveStatus.SUCCESS,
                final_assignment=final_assignment,
                solve_steps=solve_steps,
            )

        while len(flipped) < self.engine.get_map_size():
            try:
                full_assignment_result = self.assign_from_formula(formula)
            except ExceptionBrokenClues:
                return LevelSolveResult(
                    status=LevelSolveStatus.INCONSISTENT,
                    final_assignment=final_assignment,
                    solve_steps=solve_steps,
                )

            confirmed_assignments = full_assignment_result.confirmed_assignments
            final_assignment.update(
                confirmed_assignments
            )  # Includes overlapping assignments, but doesn't matter
            unflipped_confirmed_assignments = (
                self._remove_flipped_from_confirmed_assignments(
                    confirmed_assignments, flipped
                )
            )

            if len(unflipped_confirmed_assignments) == 0:
                return LevelSolveResult(
                    status=LevelSolveStatus.STUCK,
                    final_assignment=final_assignment,
                    solve_steps=solve_steps,
                )

            final_assignment.update(unflipped_confirmed_assignments)

            revealed_clues = self._flip_people_and_collect_clues(
                formula, unflipped_confirmed_assignments
            )

            step_assignment_result = self._remove_flipped_from_assignment_result(
                full_assignment_result, flipped
            )
            level_solve_step = LevelSolveStepResult(
                current_formula=deepcopy(formula),
                current_indices_flipped=flipped.copy(),
                assignment_result=step_assignment_result,
                revealed_clues=revealed_clues,
            )
            solve_steps.append(level_solve_step)
            formula.extend(self._build_formula_from_clues(revealed_clues))
            formula.extend(
                [
                    [index] if is_criminal else [-index]
                    for index, is_criminal in unflipped_confirmed_assignments.items()
                ]
            )
            flipped.update(unflipped_confirmed_assignments)

        return LevelSolveResult(
            LevelSolveStatus.SUCCESS,
            final_assignment,
            solve_steps,
        )

    def unique_check(self, formula: Formula) -> bool:
        DPLL_SAT_solver = DpllSatSolver(self.engine.get_map_size())
        SAT_solve_result = DPLL_SAT_solver.SAT_solve(formula)

        if not SAT_solve_result.is_SAT:
            return False

        possible_assignment = SAT_solve_result.possible_assignment
        assert possible_assignment is not None
        assert len(possible_assignment) == self.engine.get_map_size()

        counter_clause: Clause = [
            -index if value else index for index, value in possible_assignment.items()
        ]
        extended_formula = formula + [counter_clause]

        SAT_solve_result = DPLL_SAT_solver.SAT_solve(extended_formula)
        is_unique = not SAT_solve_result.is_SAT

        return is_unique

    def _remove_flipped_from_assignment_result(
        self, assignment_result: AssignmentResult, flipped: set[int]
    ) -> AssignmentResult:
        indices_confirmed_by_propagation = sorted(
            set(assignment_result.indices_confirmed_by_propagation) - flipped
        )
        indices_confirmed_by_SAT_calls = sorted(
            set(assignment_result.indices_confirmed_by_SAT_calls) - flipped
        )
        indices_unknown_by_SAT_calls = sorted(
            set(assignment_result.indices_unknown_by_SAT_calls) - flipped
        )
        assignment = self._remove_flipped_from_confirmed_assignments(
            assignment_result.confirmed_assignments, flipped
        )
        return AssignmentResult(
            indices_confirmed_by_propagation,
            indices_confirmed_by_SAT_calls,
            indices_unknown_by_SAT_calls,
            assignment_result.events_to_reach_possible_assignment,
            assignment,
        )

    def _use_SAT_calls_to_assign_indices(
        self,
        indices: list[int],
        formula: Formula,
        possible_assignment: Assignment,
    ) -> Assignment:
        classified_people: Assignment = {}

        for index in sorted(indices):
            SAT_call_result = SATCaller.SAT_call(
                formula,
                index,
                was_criminal_in_one_possible_assignment=possible_assignment[index],
            )

            if SAT_call_result != SATCallResult.UNKNOWN:
                classified_people[index] = SAT_call_result == SATCallResult.CRIMINAL

        return classified_people

    def _remove_flipped_from_confirmed_assignments(
        self, confirmed_assignments: Assignment, flipped: set[int]
    ) -> Assignment:
        unflipped_confirmed_assignments = {
            index: is_criminal
            for index, is_criminal in confirmed_assignments.items()
            if index not in flipped
        }

        return unflipped_confirmed_assignments

    def _flip_people_and_collect_clues(
        self,
        formula: Formula,
        unflipped_confirmed_assignments: Assignment,
    ) -> list[Clue]:
        revealed_clues: list[Clue] = []

        for index, is_criminal in unflipped_confirmed_assignments.items():
            verdict, clue = self.engine.validate_verdict_and_provide_clue_if_correct(
                formula, index, is_criminal
            )

            assert verdict == VerdictResult.CORRECT
            assert clue is not None
            revealed_clues.append(clue)

        return revealed_clues

    def _SAT_solve_formula(self, formula: Formula, map_size: int) -> SATSolveResult:
        DPLL_SAT_solver = DpllSatSolver(map_size)

        SAT_result = DPLL_SAT_solver.SAT_solve(formula)

        if not SAT_result.is_SAT:
            raise ExceptionBrokenClues("Clues are inconsistent.")
        assert SAT_result.confirmed_literals is not None
        assert SAT_result.possible_assignment is not None

        return SAT_result

    def _convert_literals_to_assignment(
        self, confirmed_literals: list[int]
    ) -> Assignment:
        return {abs(literal): literal > 0 for literal in confirmed_literals}

    def _build_formula_from_clues(self, clues: list[Clue]) -> Formula:
        formula: Formula = []

        for clue in clues:
            formula.extend(clue.to_cnf())

        return formula

    def _get_indices_in_formula(self, formula: Formula) -> set[int]:
        return {abs(literal) for clause in formula for literal in clause}
