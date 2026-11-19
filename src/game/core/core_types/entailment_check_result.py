from dataclasses import dataclass
from enum import Enum

from src.game.core.core_types.SAT_solve_result import SATSolveEvents


class EntailmentCheckStatus(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"


@dataclass
class EntailmentCheckResult:
    status: EntailmentCheckStatus
    events: SATSolveEvents
