"""Kiểm thử bộ nạp màn chơi và lớp ``Level``.

Bộ kiểm thử xác nhận 30 màn hiện có đều hợp lệ, có lời giải duy nhất, đồng
thời kiểm tra các trường hợp dữ liệu sai phải bị từ chối.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.game.clue.clue_type import ClueType
from src.game.clue.concrete_clues.implies_clue import ImpliesClue
from src.game.clue.concrete_clues.parity_clue import ParityClue
from src.game.core.core_types.exceptions import ExceptionInvalidLevel
from src.game.core.level_loader import LevelLoader
from tests.helpers import (
    MAPS_DIR,
    hidden_solution,
    level_paths,
    load_level,
)

LEVEL_PATHS = level_paths()
BASE_LEVEL = json.loads(
    (MAPS_DIR / "level_01.json").read_text(encoding="utf-8")
)


def write_level(tmp_path: Path, data: dict, name: str = "level_test.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def first_parity_clue(clue):
    if isinstance(clue, ParityClue):
        return clue
    if isinstance(clue, ImpliesClue):
        return first_parity_clue(clue.conclusion)
    return None


@pytest.mark.parametrize("path", LEVEL_PATHS, ids=lambda path: path.stem)
def test_all_levels_load_and_are_solveable(path: Path) -> None:
    level, solveable = load_level(path.name)
    data = json.loads(path.read_text(encoding="utf-8"))
    size = data["size"]
    map_size = level.get_map_size()

    assert solveable
    assert map_size == size**2
    assert len(level.map) == size
    assert all(len(row) == size for row in level.map)
    assert len(level.get_initially_revealed_region()) > 0
    assert all(
        1 <= index <= map_size
        for index in level.get_initially_revealed_region()
    )

    names = [
        level.get_person(index).get_name()
        for index in range(1, map_size + 1)
    ]
    assert len(set(names)) == len(names)
    assert names == sorted(names)

    solution = hidden_solution(level)
    for index in range(1, map_size + 1):
        clue = level.get_person(index).get_clue()
        assert clue.is_valid_with_map(map_size)
        assert clue.evaluate(solution)
        name, occupation, description = level.describe_person(index)
        assert name
        assert occupation
        assert description


def test_level_metadata_covers_every_level() -> None:
    metadata = json.loads(
        (MAPS_DIR / "level_metadata.json").read_text(encoding="utf-8-sig")
    )

    assert set(metadata) == {path.name for path in LEVEL_PATHS}
    for entry in metadata.values():
        assert entry["title"].strip()
        assert isinstance(entry.get("subtitle", ""), str)


def test_get_person_maps_row_major(level_01) -> None:
    expected_names = [
        "Alice",
        "Bob",
        "Carol",
        "Dave",
        "Eve",
        "Frank",
        "Grace",
        "Heidi",
        "Ivan",
    ]
    expected_statuses = [
        False,
        True,
        True,
        False,
        True,
        False,
        False,
        True,
        True,
    ]

    assert level_01.get_map_size() == 9
    assert [
        level_01.get_person(index).get_name()
        for index in range(1, 10)
    ] == expected_names
    assert [
        level_01.get_person(index).get_is_criminal()
        for index in range(1, 10)
    ] == expected_statuses
    assert level_01.get_person(1).get_name() == "Alice"
    assert level_01.get_person(3).get_name() == "Carol"
    assert level_01.get_person(4).get_name() == "Dave"
    assert level_01.get_person(9).get_name() == "Ivan"


def test_describe_person_returns_english_clue_sentence(level_01) -> None:
    assert level_01.describe_person(1) == (
        "Alice",
        "Artist",
        "Exactly 1 people among Dave, Eve, Frank, Grace are criminals.",
    )
    assert level_01.describe_person(3) == (
        "Carol",
        "Banker",
        "Carol is a criminal.",
    )


def test_describe_person_for_each_clue_type() -> None:
    descriptions: dict[ClueType, str] = {}
    for path in LEVEL_PATHS:
        level, _ = load_level(path.name)
        for index in range(1, level.get_map_size() + 1):
            clue = level.get_person(index).get_clue()
            if clue.get_type() not in descriptions:
                descriptions[clue.get_type()] = level.describe_person(index)[2]

    assert set(descriptions) == set(ClueType)
    assert "criminal" in descriptions[ClueType.FACT]
    assert "same role" in descriptions[ClueType.SAME]
    assert "different roles" in descriptions[ClueType.DIFFERENT]
    assert "Exactly" in descriptions[ClueType.EXACTLY]
    assert "At least" in descriptions[ClueType.AT_LEAST]
    assert "At most" in descriptions[ClueType.AT_MOST]
    assert "If " in descriptions[ClueType.IMPLIES]
    assert "then:" in descriptions[ClueType.IMPLIES]
    assert "Among" in descriptions[ClueType.COMPARE]
    assert "criminals" in descriptions[ClueType.COMPARE]
    assert "number of people" in descriptions[ClueType.PARITY]
    assert "criminal" in descriptions[ClueType.PARITY]


@pytest.mark.parametrize("path", LEVEL_PATHS, ids=lambda path: path.stem)
def test_auxiliary_indices_are_above_primary_and_do_not_overlap(
    path: Path,
) -> None:
    level, _ = load_level(path.name)
    map_size = level.get_map_size()
    next_auxiliary = map_size + 1

    for index in range(1, map_size + 1):
        clue = level.get_person(index).get_clue()
        parity_clue = first_parity_clue(clue)
        if parity_clue is None:
            assert clue.get_auxiliary_count() == 0
            continue

        assert parity_clue.first_auxiliary_index == next_auxiliary
        assert parity_clue.first_auxiliary_index > map_size
        next_auxiliary += clue.get_auxiliary_count()

    assert next_auxiliary - (map_size + 1) == level.get_auxiliary_count()


def test_load_level_without_initial_reveal_is_rejected(tmp_path: Path) -> None:
    data = copy.deepcopy(BASE_LEVEL)
    data["initially_revealed"] = []

    with pytest.raises(ExceptionInvalidLevel):
        LevelLoader.load_level_from_file(write_level(tmp_path, data))


def test_load_level_with_out_of_range_initial_reveal_is_rejected(
    tmp_path: Path,
) -> None:
    data = copy.deepcopy(BASE_LEVEL)
    data["initially_revealed"] = [99]

    with pytest.raises(ExceptionInvalidLevel):
        LevelLoader.load_level_from_file(write_level(tmp_path, data))


def test_load_level_with_unsorted_names_is_rejected(tmp_path: Path) -> None:
    data = copy.deepcopy(BASE_LEVEL)
    data["people"][0]["name"], data["people"][1]["name"] = (
        data["people"][1]["name"],
        data["people"][0]["name"],
    )

    with pytest.raises(ExceptionInvalidLevel):
        LevelLoader.load_level_from_file(write_level(tmp_path, data))


def test_load_level_with_duplicate_names_is_rejected(tmp_path: Path) -> None:
    data = copy.deepcopy(BASE_LEVEL)
    data["people"][1]["name"] = data["people"][0]["name"]

    with pytest.raises(ExceptionInvalidLevel):
        LevelLoader.load_level_from_file(write_level(tmp_path, data))


def test_load_level_with_out_of_range_clue_is_rejected(tmp_path: Path) -> None:
    data = copy.deepcopy(BASE_LEVEL)
    data["people"][0]["clue"] = {
        "type": "FACT",
        "region": [99],
        "is_criminal": True,
    }

    with pytest.raises(ExceptionInvalidLevel):
        LevelLoader.load_level_from_file(write_level(tmp_path, data))


def test_load_level_with_false_clue_is_rejected(tmp_path: Path) -> None:
    data = copy.deepcopy(BASE_LEVEL)
    data["people"][0]["clue"] = {
        "type": "FACT",
        "region": [1],
        "is_criminal": True,
    }

    with pytest.raises(ExceptionInvalidLevel):
        LevelLoader.load_level_from_file(write_level(tmp_path, data))


def test_ambiguous_level_is_loaded_but_marked_not_solveable(
    tmp_path: Path,
) -> None:
    data = {
        "size": 2,
        "initially_revealed": [1],
        "people": [
            {
                "name": "Alice",
                "occupation": "Artist",
                "is_criminal": False,
                "clue": {
                    "type": "AT_LEAST",
                    "region": [1],
                    "k": 0,
                },
            },
            {
                "name": "Bob",
                "occupation": "Baker",
                "is_criminal": True,
                "clue": {
                    "type": "AT_LEAST",
                    "region": [2],
                    "k": 0,
                },
            },
            {
                "name": "Carol",
                "occupation": "Chef",
                "is_criminal": False,
                "clue": {
                    "type": "AT_LEAST",
                    "region": [3],
                    "k": 0,
                },
            },
            {
                "name": "Dave",
                "occupation": "Doctor",
                "is_criminal": True,
                "clue": {
                    "type": "AT_LEAST",
                    "region": [4],
                    "k": 0,
                },
            },
        ],
    }

    level, solveable = LevelLoader.load_level_from_file(
        write_level(tmp_path, data)
    )

    assert level.get_map_size() == 4
    assert not solveable


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "level_broken.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        LevelLoader.load_level_from_file(path)


def test_missing_level_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        LevelLoader.load_level_from_file(tmp_path / "missing.json")
