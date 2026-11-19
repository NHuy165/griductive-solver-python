from src.game.core.core_types.assignment_result import AssignmentResult
from src.game.core.core_types.SAT_solve_result import (
    SATSolveEvent,
    SATSolveEvents,
    SATSolveResult,
)


def count_events(events: SATSolveEvents) -> dict[SATSolveEvent, int]:
    result: dict[SATSolveEvent, int] = {
        SATSolveEvent.PROPAGATION: 0,
        SATSolveEvent.DECISION: 0,
        SATSolveEvent.BACKTRACK: 0,
    }

    for event, _ in events:
        result[event] += 1
    return result


def count_events_from_SAT_solve(
    SAT_solve_result: SATSolveResult,
) -> dict[SATSolveEvent, int]:
    return count_events(SAT_solve_result.events)


def count_events_from_assignment_result(
    assignment_result: AssignmentResult,
) -> dict[SATSolveEvent, int]:
    def add_counts(
        main_dict: dict[SATSolveEvent, int], other_dict: dict[SATSolveEvent, int]
    ) -> dict[SATSolveEvent, int]:
        for event, count in other_dict.items():
            main_dict[event] += count
        return main_dict

    result: dict[SATSolveEvent, int] = {
        SATSolveEvent.PROPAGATION: 0,
        SATSolveEvent.DECISION: 0,
        SATSolveEvent.BACKTRACK: 0,
    }

    possible_assignment_event_counts = count_events(
        assignment_result.events_to_reach_possible_assignment
    )
    result = add_counts(result, possible_assignment_event_counts)

    for events in assignment_result.events_in_entailment_checks.values():
        current_event_counts = count_events(events)
        result = add_counts(result, current_event_counts)

    return result
