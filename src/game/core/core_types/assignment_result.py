from dataclasses import dataclass

from src.game.core.core_types.miscellaneous import Assignment
from src.game.core.core_types.SAT_solve_result import SATSolveEvents


@dataclass
class AssignmentResult:
    indices_confirmed_by_propagation: list[int]
    indices_confirmed_by_entailment_checks: list[int]
    indices_unknown_by_entailment_checks: list[int]
    events_to_reach_possible_assignment: SATSolveEvents
    events_in_entailment_checks: dict[int, SATSolveEvents]
    confirmed_assignments: Assignment

    def __post_init__(self) -> None:
        assert len(self.events_in_entailment_checks) == len(
            self.indices_confirmed_by_entailment_checks
        ) + len(self.indices_unknown_by_entailment_checks)
