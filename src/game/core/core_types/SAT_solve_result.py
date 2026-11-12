from dataclasses import dataclass
from enum import Enum

from src.game.core.miscellaneous import Assignment


class SATSolveEvent(str, Enum):
    PROPAGATION = "PROPAGATION"
    DECISION = "DECISION"
    BACKTRACK = "BACKTRACK"


SATSolveEvents = list[tuple[SATSolveEvent, int]]


@dataclass
class SATSolveResult:
    is_SAT: bool
    confirmed_literals: list[int] | None
    possible_assignment: Assignment | None
    events: SATSolveEvents | None
