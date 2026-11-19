from src.game.core.core_types.assignment_result import AssignmentResult
from src.game.core.core_types.level_solve_result import LevelSolveResult


def count_SAT_solves_from_assignment_result(
    assignment_result: AssignmentResult,
) -> int:
    return (
        len(assignment_result.non_auxiliary_indices_confirmed_by_entailment_checks)
        + len(assignment_result.non_auxiliary_indices_unknown_by_entailment_checks)
        + 1
    )


def count_SAT_solves_from_level_solve(
    level_solve_result: LevelSolveResult,
) -> int:
    num_SAT_solves_from_steps = [
        count_SAT_solves_from_assignment_result(step.assignment_result)
        for step in level_solve_result.solve_steps
    ]
    return sum(num_SAT_solves_from_steps)
