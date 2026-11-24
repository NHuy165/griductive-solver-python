from src.game.core.core_types.level_solve_result import LevelSolveResult


def count_reveal_waves_from_level_solve(
    level_solve_result: LevelSolveResult,
) -> int:
    return len(level_solve_result.solve_steps)
