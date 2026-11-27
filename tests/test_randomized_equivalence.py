"""Kiểm chứng ngẫu nhiên có hạt giống cố định.

Các kiểm thử này so sánh DPLL với vét cạn và so sánh mã hóa CNF của từng
manh mối với hàm ``evaluate`` trên nhiều vùng ngẫu nhiên. Nhờ hạt giống cố
định, kết quả lặp lại được giữa các lần chạy.
"""

from __future__ import annotations

import random

from src.game.clue.concrete_clues.at_least_clue import AtLeastClue
from src.game.clue.concrete_clues.at_most_clue import AtMostClue
from src.game.clue.concrete_clues.compare_clue import CompareClue
from src.game.clue.concrete_clues.different_clue import DifferentClue
from src.game.clue.concrete_clues.exactly_clue import ExactlyClue
from src.game.clue.concrete_clues.fact_clue import FactClue
from src.game.clue.concrete_clues.implies_clue import ImpliesClue
from src.game.clue.concrete_clues.parity_clue import ParityClue
from src.game.clue.concrete_clues.same_clue import SameClue
from src.game.logic.DPLL_SAT_solver import DpllSatSolver
from tests.helpers import (
    all_assignments,
    brute_force_models,
    cnf_is_satisfiable_with_primary_assignment,
    is_cnf_satisfied,
)

SEED = 20261127


def random_region(rng: random.Random, min_size: int, max_size: int) -> list[int]:
    size = rng.randint(min_size, max_size)
    return rng.sample(range(1, 6), size)


def random_non_implies_clue(rng: random.Random):
    clue_type = rng.choice(
        [
            "FACT",
            "SAME",
            "DIFFERENT",
            "AT_LEAST",
            "AT_MOST",
            "EXACTLY",
            "COMPARE",
            "PARITY",
        ]
    )

    if clue_type == "FACT":
        return FactClue([rng.randint(1, 5)], rng.choice([True, False]))
    if clue_type == "SAME":
        return SameClue(random_region(rng, 2, 2))
    if clue_type == "DIFFERENT":
        return DifferentClue(random_region(rng, 2, 2))
    if clue_type == "AT_LEAST":
        region = random_region(rng, 1, 4)
        return AtLeastClue(region, rng.randint(0, len(region)))
    if clue_type == "AT_MOST":
        region = random_region(rng, 1, 4)
        return AtMostClue(region, rng.randint(0, len(region)))
    if clue_type == "EXACTLY":
        region = random_region(rng, 1, 4)
        return ExactlyClue(region, rng.randint(0, len(region)))
    if clue_type == "COMPARE":
        return CompareClue(
            random_region(rng, 1, 4),
            random_region(rng, 1, 4),
            rng.choice([True, False]),
        )
    return ParityClue(random_region(rng, 1, 4), rng.choice([True, False]))


def random_clue(rng: random.Random):
    if rng.random() < 0.25:
        premise = rng.randint(1, 5)
        conclusion = random_non_implies_clue(rng)
        return ImpliesClue(
            [premise],
            rng.choice([True, False]),
            conclusion,
        )
    return random_non_implies_clue(rng)


def assert_encoding_matches_semantics(clue) -> None:
    primary_indices = sorted(set(clue.get_region()))
    for assignment in all_assignments(primary_indices):
        expected = clue.evaluate(assignment)
        actual = cnf_is_satisfiable_with_primary_assignment(
            clue.to_cnf(), assignment
        )
        assert actual == expected, (
            clue.get_type(),
            primary_indices,
            assignment,
            expected,
            actual,
        )


def test_random_dpll_matches_brute_force() -> None:
    rng = random.Random(SEED)

    for _ in range(200):
        num_variables = rng.randint(1, 5)
        clauses: list[list[int]] = []
        for _ in range(rng.randint(0, 12)):
            clause = []
            for _ in range(rng.randint(1, 3)):
                variable = rng.randint(1, num_variables)
                clause.append(variable if rng.random() < 0.5 else -variable)
            clauses.append(clause)

        result = DpllSatSolver(num_variables).SAT_solve(clauses)
        models = list(brute_force_models(clauses, num_variables))

        assert result.is_SAT == bool(models)

        if result.is_SAT:
            assert result.possible_assignment is not None
            assert set(result.possible_assignment) == set(
                range(1, num_variables + 1)
            )
            assert is_cnf_satisfied(clauses, result.possible_assignment)

            repeated = DpllSatSolver(num_variables).SAT_solve(clauses)
            assert repeated.is_SAT == result.is_SAT
            assert repeated.confirmed_literals == result.confirmed_literals
            assert repeated.possible_assignment == result.possible_assignment
            assert repeated.events == result.events
        else:
            assert result.confirmed_literals is None
            assert result.possible_assignment is None


def test_random_confirmed_literals_are_entailed() -> None:
    rng = random.Random(SEED + 1)

    for _ in range(100):
        num_variables = rng.randint(1, 5)
        clauses: list[list[int]] = []
        for _ in range(rng.randint(0, 10)):
            clause = []
            for _ in range(rng.randint(1, 3)):
                variable = rng.randint(1, num_variables)
                clause.append(variable if rng.random() < 0.5 else -variable)
            clauses.append(clause)

        result = DpllSatSolver(num_variables).SAT_solve(clauses)
        if not result.is_SAT:
            continue

        models = list(brute_force_models(clauses, num_variables))
        assert models
        for literal in result.confirmed_literals or []:
            for model in models:
                assert model[abs(literal)] == (literal > 0)


def test_random_clue_encodings_match_truth_tables() -> None:
    rng = random.Random(SEED + 2)

    for _ in range(80):
        clue = random_clue(rng)
        clue.set_first_auxiliary_index(6)
        assert_encoding_matches_semantics(clue)


def test_random_compare_encodings_with_overlapping_regions() -> None:
    rng = random.Random(SEED + 3)

    for _ in range(40):
        clue = CompareClue(
            random_region(rng, 1, 4),
            random_region(rng, 1, 4),
            rng.choice([True, False]),
        )
        assert_encoding_matches_semantics(clue)


def test_random_implies_with_parity_conclusion() -> None:
    rng = random.Random(SEED + 4)

    for _ in range(30):
        conclusion = ParityClue(random_region(rng, 1, 4), rng.choice([True, False]))
        clue = ImpliesClue(
            [rng.randint(1, 5)],
            rng.choice([True, False]),
            conclusion,
        )
        clue.set_first_auxiliary_index(6)
        assert_encoding_matches_semantics(clue)
