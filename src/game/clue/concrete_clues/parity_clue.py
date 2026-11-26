from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.core.core_types.miscellaneous import Assignment, Formula


class ParityClue(Clue):
    def __init__(self, region: list[int], is_odd: bool) -> None:
        assert len(region) > 0
        assert len(set(region)) == len(region)

        super().__init__(region)
        self.is_odd = is_odd
        self.first_auxiliary_index = 0
        self.type = ClueType.PARITY

    def get_auxiliary_count(self) -> int:
        return len(self.region) - 1

    def set_first_auxiliary_index(self, first_auxiliary_index: int) -> None:
        self.first_auxiliary_index = first_auxiliary_index

    def to_cnf(self) -> Formula:
        assert self.first_auxiliary_index > 0

        formula: Formula = []

        running_xor = self.region[0]
        offset = 0
        for index in self.region[1:]:
            auxiliary_index = self.first_auxiliary_index + offset

            formula.extend(
                self._convert_xor_expression_into_cnf(
                    running_xor, index, auxiliary_index
                )
            )

            running_xor = auxiliary_index
            offset += 1

        formula.append([running_xor] if self.is_odd else [-running_xor])

        return formula

    def evaluate(self, assignment: Assignment) -> bool:
        num_criminals = sum(assignment[index] for index in self.region)

        return (num_criminals % 2 == 1) == self.is_odd

    def is_valid_with_map(self, map_size: int) -> bool:
        all_in_range = all(0 < index <= map_size for index in self.region)

        return all_in_range

    def _convert_xor_expression_into_cnf(
        self, first: int, second: int, result: int
    ) -> Formula:
        return [
            [-first, -second, -result],
            [first, second, -result],
            [first, -second, result],
            [-first, second, result],
        ]
