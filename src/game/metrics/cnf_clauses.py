from src.game.core.core_types.level_solve_result import LevelSolveStepResult
from src.game.core.core_types.miscellaneous import Formula


def count_cnf_clauses_from_formula(formula: Formula) -> int:
    return len(formula)


def count_cnf_clauses_generated_at_step(
    level_solve_step: LevelSolveStepResult,
) -> int:
    # Only counts clauses generated from revealed clues, not unit clauses from the revealed people themselves.
    num_clauses_from_clues = [
        count_cnf_clauses_from_formula(clue.to_cnf())
        for clue in level_solve_step.revealed_clues
    ]
    return sum(num_clauses_from_clues)
