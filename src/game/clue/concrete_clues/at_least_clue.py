from itertools import combinations

from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.core.core_types.miscellaneous import Assignment, Formula


class AtLeastClue(Clue):
    def __init__(self, region: list[int], k: int) -> None:
        assert len(region) > 0
        assert len(region) >= k >= 0
        assert len(set(region)) == len(region)

        super().__init__(region)
        self.k = k
        self.type = ClueType.AT_LEAST

    def to_cnf(self) -> Formula:
        formula: Formula = []

        formula.extend(self._groups_of_n_minus_k_plus_1_contain_criminal())

        return formula

    def evaluate(self, assignment: Assignment) -> bool:
        num_criminals = sum(assignment[index] for index in self.region)

        return num_criminals >= self.k

    def is_valid_with_map(self, map_size: int) -> bool:
        all_in_range = all(0 < index <= map_size for index in self.region)

        return all_in_range

    def _groups_of_n_minus_k_plus_1_contain_criminal(self) -> Formula:
        formula: Formula = []

        n = len(self.region)
        groups_of_n_minus_k_plus_1 = combinations(self.region, n - self.k + 1)
        for group in groups_of_n_minus_k_plus_1:
            formula.append([index for index in group])

        return formula
