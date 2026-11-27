"""Kiểm thử phần mô tả manh mối tiếng Việt cho giao diện web."""

from __future__ import annotations

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
from src.web.clue_text import _name, _names, describe_clue_vi
from tests.helpers import level_paths, load_level


def first_clue_of_type(clue_type: ClueType):
    for path in level_paths():
        level, _ = load_level(path.name)
        for index in range(1, level.get_map_size() + 1):
            clue = level.get_person(index).get_clue()
            if clue.get_type() == clue_type:
                return level, clue
    raise AssertionError(f"Không tìm thấy manh mối {clue_type}.")


def test_first_clue_of_each_type_has_vietnamese_description() -> None:
    expected_keywords = {
        ClueType.FACT: ["tội phạm"],
        ClueType.SAME: ["cùng vai trò"],
        ClueType.DIFFERENT: ["khác nhau"],
        ClueType.EXACTLY: ["tội phạm"],
        ClueType.AT_LEAST: ["tội phạm"],
        ClueType.AT_MOST: ["tội phạm"],
        ClueType.IMPLIES: ["Nếu", "thì:"],
        ClueType.COMPARE: ["Số tội phạm"],
        ClueType.PARITY: ["Số tội phạm"],
    }

    for clue_type, keywords in expected_keywords.items():
        level, clue = first_clue_of_type(clue_type)
        text = describe_clue_vi(level, clue)
        assert text
        assert text.endswith(".")
        for keyword in keywords:
            assert keyword in text


def test_every_clue_in_every_level_is_describable() -> None:
    for path in level_paths():
        level, _ = load_level(path.name)
        for index in range(1, level.get_map_size() + 1):
            clue = level.get_person(index).get_clue()
            text = describe_clue_vi(level, clue)
            assert text
            assert text.endswith(".")


def test_name_helpers(level_01) -> None:
    assert _name(level_01, 1) == "Alice"
    assert _names(level_01, [1]) == "Alice"
    assert _names(level_01, [1, 2]) == "Alice và Bob"
    assert _names(level_01, [1, 2, 3]) == "Alice, Bob và Carol"


def test_fact_descriptions(level_01) -> None:
    assert describe_clue_vi(level_01, FactClue([1], True)) == (
        "Alice là tội phạm."
    )
    assert describe_clue_vi(level_01, FactClue([1], False)) == (
        "Alice không phải tội phạm."
    )


def test_same_and_different_descriptions(level_01) -> None:
    assert describe_clue_vi(level_01, SameClue([1, 2])) == (
        "Alice và Bob có cùng vai trò."
    )
    assert describe_clue_vi(level_01, DifferentClue([1, 2])) == (
        "Alice và Bob có vai trò khác nhau."
    )


def test_exactly_boundary_descriptions(level_01) -> None:
    assert describe_clue_vi(level_01, ExactlyClue([1, 2], 0)) == (
        "Không ai trong nhóm Alice và Bob là tội phạm."
    )
    assert describe_clue_vi(level_01, ExactlyClue([1, 2], 2)) == (
        "Tất cả Alice và Bob đều là tội phạm."
    )


def test_at_least_boundary_description(level_01) -> None:
    assert describe_clue_vi(level_01, AtLeastClue([1, 2], 0)) == (
        "Không có ràng buộc về số tội phạm trong nhóm Alice và Bob."
    )


def test_at_most_boundary_descriptions(level_01) -> None:
    assert describe_clue_vi(level_01, AtMostClue([1, 2], 0)) == (
        "Không ai trong nhóm Alice và Bob là tội phạm."
    )
    assert describe_clue_vi(level_01, AtMostClue([1, 2], 2)) == (
        "Tất cả Alice và Bob đều có thể là tội phạm."
    )


def test_compare_descriptions(level_01) -> None:
    equal = CompareClue([1, 2], [2, 3], True)
    more = CompareClue([1, 2], [2, 3], False)

    assert describe_clue_vi(level_01, equal) == (
        "Số tội phạm trong nhóm Alice và Bob bằng số tội phạm "
        "trong nhóm Bob và Carol."
    )
    assert describe_clue_vi(level_01, more) == (
        "Số tội phạm trong nhóm Alice và Bob nhiều hơn "
        "trong nhóm Bob và Carol."
    )


def test_parity_descriptions(level_01) -> None:
    assert describe_clue_vi(level_01, ParityClue([1, 2], True)) == (
        "Số tội phạm trong nhóm Alice và Bob là số lẻ."
    )
    assert describe_clue_vi(level_01, ParityClue([1, 2], False)) == (
        "Số tội phạm trong nhóm Alice và Bob là số chẵn."
    )


def test_implies_descriptions(level_01) -> None:
    criminal_premise = ImpliesClue([1], True, FactClue([2], True))
    innocent_premise = ImpliesClue([1], False, FactClue([2], True))

    assert describe_clue_vi(level_01, criminal_premise) == (
        "Nếu Alice là tội phạm, thì: Bob là tội phạm."
    )
    assert describe_clue_vi(level_01, innocent_premise) == (
        "Nếu Alice không phải tội phạm, thì: Bob là tội phạm."
    )
