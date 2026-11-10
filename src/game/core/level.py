from collections.abc import Callable
from typing import cast

from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.clue.concrete_clues.at_least_clue import AtLeastClue
from src.game.clue.concrete_clues.at_most_clue import AtMostClue
from src.game.clue.concrete_clues.different_clue import DifferentClue
from src.game.clue.concrete_clues.exactly_clue import ExactlyClue
from src.game.clue.concrete_clues.fact_clue import FactClue
from src.game.clue.concrete_clues.same_clue import SameClue
from src.game.core.person import Person


class Level:
    def __init__(
        self,
        map: list[list[Person]],
        initially_revealed_region: list[int],
    ) -> None:
        self.map = map
        self.initially_revealed_region = initially_revealed_region

    def get_map_size(self) -> int:
        return len(self.map) ** 2

    def get_person(self, index: int) -> Person:
        index -= 1
        map_width = len(self.map[0])

        row = index // map_width
        col = index % map_width

        return self.map[row][col]

    def get_initially_revealed_region(self) -> list[int]:
        return self.initially_revealed_region

    def describe_person(self, index: int) -> tuple[str, str, str]:
        CLUE_DESCRIPTION_MAP: dict[ClueType, Callable[[Clue], str]] = {
            ClueType.FACT: self._describe_fact_clue,
            ClueType.SAME: self._describe_same_clue,
            ClueType.DIFFERENT: self._describe_different_clue,
            ClueType.EXACTLY: self._describe_exactly_clue,
            ClueType.AT_LEAST: self._describe_at_least_clue,
            ClueType.AT_MOST: self._describe_at_most_clue,
        }

        person = self.get_person(index)
        clue = person.get_clue()
        describer = CLUE_DESCRIPTION_MAP[clue.get_type()]
        described_clue = describer(clue)

        return (person.get_name(), person.get_occupation(), described_clue)

    def _describe_fact_clue(self, clue: Clue) -> str:
        fact_clue = cast(FactClue, clue)
        name = self._get_name(fact_clue.region[0])
        role = "a criminal" if fact_clue.is_criminal else "not a criminal"

        return f"{name} is {role}."

    def _describe_same_clue(self, clue: Clue) -> str:
        same_clue = cast(SameClue, clue)
        first_name = self._get_name(same_clue.region[0])
        second_name = self._get_name(same_clue.region[1])

        return f"{first_name} and {second_name} have the same role."

    def _describe_different_clue(self, clue: Clue) -> str:
        different_clue = cast(DifferentClue, clue)
        first_name = self._get_name(different_clue.region[0])
        second_name = self._get_name(different_clue.region[1])

        return f"{first_name} and {second_name} have different roles."

    def _describe_exactly_clue(self, clue: Clue) -> str:
        exactly_clue = cast(ExactlyClue, clue)
        names = self._join_names(exactly_clue.region)

        return f"Exactly {exactly_clue.k} people among {names} are criminals."

    def _describe_at_least_clue(self, clue: Clue) -> str:
        at_least_clue = cast(AtLeastClue, clue)
        names = self._join_names(at_least_clue.region)

        return f"At least {at_least_clue.k} people among {names} are criminals."

    def _describe_at_most_clue(self, clue: Clue) -> str:
        at_most_clue = cast(AtMostClue, clue)
        names = self._join_names(at_most_clue.region)

        return f"At most {at_most_clue.k} people among {names} are criminals."

    def _join_names(self, region: list[int]) -> str:
        names = [self._get_name(index) for index in region]

        return f"{', '.join(names)}"

    def _get_name(self, index: int) -> str:
        return self.get_person(index).get_name()
