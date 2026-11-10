from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.core.core_types import Assignment, Formula


class FactClue(Clue):
    def __init__(self, region: list[int], is_criminal: bool) -> None:
        assert len(region) == 1
        super().__init__(region)

        self.is_criminal = is_criminal
        self.type = ClueType.FACT

    def to_cnf(self) -> Formula:
        index = self.region[0]

        return [[index]] if self.is_criminal else [[-index]]

    def evaluate(self, assignment: Assignment) -> bool:
        index = self.region[0]
        index_role = assignment[index]

        return index_role == self.is_criminal

    def is_valid_with_map(self, map_size: int) -> bool:
        index = self.region[0]

        return 0 < index <= map_size
