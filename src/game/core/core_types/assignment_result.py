from dataclasses import dataclass

from src.game.core.core_types.miscellaneous import Assignment


@dataclass
class AssignmentResult:
    indices_confirmed_by_propagation: list[int]
    indices_confirmed_by_SAT_calls: list[int]
    indices_unknown_by_SAT_calls: list[int]
    assignment: Assignment
