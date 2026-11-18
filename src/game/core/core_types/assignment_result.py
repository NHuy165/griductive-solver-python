from dataclasses import dataclass

from src.game.core.core_types.miscellaneous import Assignment
from src.game.core.core_types.SAT_solve_result import SATSolveEvents


@dataclass
class AssignmentResult:
    indices_confirmed_by_propagation: list[int]
    indices_confirmed_by_SAT_calls: list[int]
    indices_unknown_by_SAT_calls: list[int]
    events_to_reach_possible_assignment: SATSolveEvents
    confirmed_assignments: Assignment
