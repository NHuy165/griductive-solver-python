"""Vietnamese descriptions for the clues shown in the web interface.

The game engine stores and describes clues in English.  The interface is in
Vietnamese, so this module renders the same clue objects as natural Vietnamese
sentences.  It only reads public clue data: type, region and parameters.
"""

from __future__ import annotations

from typing import cast

from src.game.clue.clue import Clue
from src.game.clue.clue_type import ClueType
from src.game.clue.concrete_clues.at_least_clue import AtLeastClue
from src.game.clue.concrete_clues.at_most_clue import AtMostClue
from src.game.clue.concrete_clues.compare_clue import CompareClue
from src.game.clue.concrete_clues.different_clue import DifferentClue
from src.game.clue.concrete_clues.exactly_clue import ExactlyClue
from src.game.clue.concrete_clues.fact_clue import FactClue
from src.game.clue.concrete_clues.implies_clue import ImpliesClue
from src.game.clue.concrete_clues.parity_clue import ParityClue
from src.game.clue.concrete_clues.same_clue import SameClue
from src.game.core.level import Level


def describe_clue_vi(level: Level, clue: Clue) -> str:
    """Return a Vietnamese sentence describing ``clue``."""

    clue_type = clue.get_type()

    if clue_type == ClueType.FACT:
        fact = cast(FactClue, clue)
        name = _name(level, fact.region[0])
        role = "là tội phạm" if fact.is_criminal else "không phải tội phạm"
        return f"{name} {role}."

    if clue_type == ClueType.SAME:
        same = cast(SameClue, clue)
        return (
            f"{_name(level, same.region[0])} và "
            f"{_name(level, same.region[1])} có cùng vai trò."
        )

    if clue_type == ClueType.DIFFERENT:
        different = cast(DifferentClue, clue)
        return (
            f"{_name(level, different.region[0])} và "
            f"{_name(level, different.region[1])} có vai trò khác nhau."
        )

    if clue_type == ClueType.EXACTLY:
        exactly = cast(ExactlyClue, clue)
        names = _names(level, exactly.region)
        if exactly.k == 0:
            return f"Không ai trong nhóm {names} là tội phạm."
        if exactly.k == len(exactly.region):
            return f"Tất cả {names} đều là tội phạm."
        return f"Đúng {exactly.k} người trong nhóm {names} là tội phạm."

    if clue_type == ClueType.AT_LEAST:
        at_least = cast(AtLeastClue, clue)
        names = _names(level, at_least.region)
        if at_least.k == 0:
            return f"Không có ràng buộc về số tội phạm trong nhóm {names}."
        return f"Ít nhất {at_least.k} người trong nhóm {names} là tội phạm."

    if clue_type == ClueType.AT_MOST:
        at_most = cast(AtMostClue, clue)
        names = _names(level, at_most.region)
        if at_most.k == 0:
            return f"Không ai trong nhóm {names} là tội phạm."
        if at_most.k == len(at_most.region):
            return f"Tất cả {names} đều có thể là tội phạm."
        return f"Nhiều nhất {at_most.k} người trong nhóm {names} là tội phạm."

    if clue_type == ClueType.IMPLIES:
        implies = cast(ImpliesClue, clue)
        premise = (
            "là tội phạm" if implies.is_criminal else "không phải tội phạm"
        )
        conclusion = describe_clue_vi(level, implies.conclusion)
        return (
            f"Nếu {_name(level, implies.region[0])} {premise}, "
            f"thì: {conclusion}"
        )

    if clue_type == ClueType.COMPARE:
        compare = cast(CompareClue, clue)
        first = _names(level, compare.region)
        second = _names(level, compare.other_region)
        if compare.equals:
            return (
                f"Số tội phạm trong nhóm {first} bằng số tội phạm "
                f"trong nhóm {second}."
            )
        return (
            f"Số tội phạm trong nhóm {first} nhiều hơn "
            f"trong nhóm {second}."
        )

    if clue_type == ClueType.PARITY:
        parity = cast(ParityClue, clue)
        names = _names(level, parity.region)
        kind = "lẻ" if parity.is_odd else "chẵn"
        return f"Số tội phạm trong nhóm {names} là số {kind}."

    return "Manh mối chưa được hỗ trợ hiển thị."


def _name(level: Level, index: int) -> str:
    return level.get_person(index).get_name()


def _names(level: Level, region: list[int]) -> str:
    names = [_name(level, index) for index in region]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} và {names[1]}"
    return f"{', '.join(names[:-1])} và {names[-1]}"
