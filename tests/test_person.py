"""Kiểm thử lớp ``Person`` — đơn vị dữ liệu của một người trên bàn."""

from __future__ import annotations

from src.game.clue.concrete_clues.fact_clue import FactClue
from src.game.core.person import Person


def test_person_getters_return_constructor_values() -> None:
    clue = FactClue([1], True)
    person = Person("Alice", "Artist", clue, False)

    assert person.get_name() == "Alice"
    assert person.get_occupation() == "Artist"
    assert person.get_clue() is clue
    assert person.get_is_criminal() is False


def test_person_getters_reflect_criminal_status() -> None:
    clue = FactClue([2], True)
    person = Person("Bob", "Baker", clue, True)

    assert person.get_name() == "Bob"
    assert person.get_occupation() == "Baker"
    assert person.get_clue() is clue
    assert person.get_is_criminal() is True
