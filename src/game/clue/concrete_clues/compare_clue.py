from itertools import product

from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.core.core_types.miscellaneous import Assignment, Formula


class CompareClue(Clue):
    def __init__(
        self, region: list[int], other_region: list[int], equals: bool
    ) -> None:
        assert len(region) > 0
        assert len(other_region) > 0
        assert len(set(region)) == len(region)
        assert len(set(other_region)) == len(other_region)

        super().__init__(region)
        self.other_region = other_region
        self.equals = equals
        self.type = ClueType.COMPARE

    def get_region(self) -> list[int]:
        return self.region + self.other_region

    def to_cnf(self) -> Formula:
        formula: Formula = []

        region_indices = list(set(self.region) - set(self.other_region))
        other_region_indices = list(set(self.other_region) - set(self.region))
        indices = region_indices + other_region_indices

        for values_combination in product([True, False], repeat=len(indices)):
            assignment = dict(zip(indices, values_combination))

            if not self._comparison_holds(
                region_indices, other_region_indices, assignment
            ):
                formula.append(self._forbid_assignment(assignment))

        return formula

    def evaluate(self, assignment: Assignment) -> bool:
        return self._comparison_holds(self.region, self.other_region, assignment)

    def is_valid_with_map(self, map_size: int) -> bool:
        all_in_range = all(
            0 < index <= map_size for index in self.region + self.other_region
        )

        return all_in_range

    def _comparison_holds(
        self,
        region_A: list[int],
        region_B: list[int],
        assignment: Assignment,
    ) -> bool:
        criminals_in_region_A = sum(assignment[index] for index in region_A)
        criminals_in_region_B = sum(assignment[index] for index in region_B)

        if self.equals:
            return criminals_in_region_A == criminals_in_region_B

        return criminals_in_region_A > criminals_in_region_B

    def _forbid_assignment(self, assignment: Assignment) -> list[int]:
        return [
            -index if is_criminal else index
            for index, is_criminal in assignment.items()
        ]
