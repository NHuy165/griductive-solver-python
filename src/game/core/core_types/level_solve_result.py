from dataclasses import dataclass

from src.game.clue.clue import Clue
from src.game.core.core_types.assignment_result import AssignmentResult
from src.game.core.core_types.miscellaneous import Assignment, Formula


@dataclass
class LevelSolveStepResult:
    current_formula: Formula
    current_indices_flipped: set[int]
    assignment_result: AssignmentResult
    revealed_clues: list[Clue]

    def __post_init__(self) -> None:
        assert len(self.revealed_clues) == len(self.assignment_result.assignment)


@dataclass
class LevelSolveResult:
    final_assignment: Assignment
    solve_steps: list[LevelSolveStepResult]
