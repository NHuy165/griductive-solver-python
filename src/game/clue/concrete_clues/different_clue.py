from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.core.core_types import Assignment, Formula


class DifferentClue(Clue):
    def __init__(self, region: list[int]) -> None:
        assert len(region) == 2
        super().__init__(region)

        self.type = ClueType.DIFFERENT

    def to_cnf(self) -> Formula:
        index_1 = self.region[0]
        index_2 = self.region[1]

        return [[index_1, index_2], [-index_1, -index_2]]

    def evaluate(self, assignment: Assignment) -> bool:
        index_1 = self.region[0]
        index_2 = self.region[1]

        return assignment[index_1] != assignment[index_2]

    def is_valid_with_map(self, map_size: int) -> bool:
        index_1 = self.region[0]
        index_2 = self.region[1]

        within_range_and_not_overlap = (
            0 < index_1 <= map_size and 0 < index_2 <= map_size and index_1 != index_2
        )

        return within_range_and_not_overlap
