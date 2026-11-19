from dataclasses import dataclass

from src.game.core.core_types.miscellaneous import Assignment
from src.game.core.core_types.SAT_solve_result import SATSolveEvents


@dataclass
class AssignmentResult:
    non_auxi_indices_confirmed_propagation: list[int]
    non_auxi_indices_confirmed_entailment: list[int]
    non_auxi_indices_unknown_entailment: list[int]
    events_to_reach_possible_assignment: SATSolveEvents
    events_in_entailment_checks: dict[int, SATSolveEvents]
    confirmed_assignments: Assignment

    def __post_init__(self) -> None:
        assert len(self.events_in_entailment_checks) == len(
            self.non_auxi_indices_confirmed_entailment
        ) + len(self.non_auxi_indices_unknown_entailment)
