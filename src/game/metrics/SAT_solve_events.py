from src.game.core.core_types.SAT_solve_result import SATSolveEvent, SATSolveResult


def count_events_from_SAT_solve(
    SAT_solve_result: SATSolveResult,
) -> dict[SATSolveEvent, int]:

    result: dict[SATSolveEvent, int] = {
        SATSolveEvent.PROPAGATION: 0,
        SATSolveEvent.DECISION: 0,
        SATSolveEvent.BACKTRACK: 0,
    }
    if SAT_solve_result.events is None:
        return result

    for event, _ in SAT_solve_result.events:
        result[event] += 1

    return result
