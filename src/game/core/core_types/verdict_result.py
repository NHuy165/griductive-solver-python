from enum import Enum


class VerdictResult(str, Enum):
    CORRECT = "CORRECT"
    CONTRADICTED = "CONTRADICTED"
    NOT_PROVABLE = "NOT_PROVABLE"
