from abc import ABC, abstractmethod

from src.game.clue.clue_type import ClueType
from src.game.core.core_types import Assignment, Formula


class Clue(ABC):
    type: ClueType

    def __init__(self, region: list[int]) -> None:
        self.region = region

    def get_region(self) -> list[int]:
        return self.region

    def get_type(self) -> ClueType:
        return self.type

    @abstractmethod
    def to_cnf(self) -> Formula:
        pass

    @abstractmethod
    def evaluate(self, assignment: Assignment) -> bool:
        pass

    @abstractmethod
    def is_valid_with_map(self, map_size: int) -> bool:
        pass
