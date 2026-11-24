from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.core.core_types.miscellaneous import Assignment, Formula


class ImpliesClue(Clue):
    def __init__(self, region: list[int], is_criminal: bool, conclusion: Clue) -> None:
        assert len(region) == 1
        super().__init__(region)

        self.is_criminal = is_criminal
        self.conclusion = conclusion
        self.type = ClueType.IMPLIES

    def get_region(self) -> list[int]:
        return list(set(self.region + self.conclusion.get_region()))

    def get_auxiliary_count(self) -> int:
        return self.conclusion.get_auxiliary_count()

    def set_first_auxiliary_index(self, first_auxiliary_index: int) -> None:
        self.conclusion.set_first_auxiliary_index(first_auxiliary_index)

    def to_cnf(self) -> Formula:
        index = self.region[0]
        negated_premise_literal = -index if self.is_criminal else index

        return [
            [negated_premise_literal, *clause] for clause in self.conclusion.to_cnf()
        ]

    def evaluate(self, assignment: Assignment) -> bool:
        index = self.region[0]
        premise_holds = assignment[index] == self.is_criminal

        return not premise_holds or self.conclusion.evaluate(assignment)

    def is_valid_with_map(self, map_size: int) -> bool:
        index = self.region[0]

        return 0 < index <= map_size and self.conclusion.is_valid_with_map(map_size)
