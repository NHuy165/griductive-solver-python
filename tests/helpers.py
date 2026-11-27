"""Các tiện ích dùng chung cho bộ kiểm thử.

Module này chỉ đọc dữ liệu và gọi API công khai của hệ thống. Mọi hàm ở đây
đều phục vụ việc kiểm chứng, không thay đổi hành vi của mã nguồn chính.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Iterable, Iterator

from src.game.core.core_types.miscellaneous import Assignment, Formula
from src.game.core.level import Level
from src.game.core.level_loader import LevelLoader
from src.game.logic.DPLL_SAT_solver import DpllSatSolver

ROOT = Path(__file__).resolve().parents[1]
MAPS_DIR = ROOT / "src" / "maps"


def level_paths() -> list[Path]:
    """Trả về danh sách 30 tệp màn chơi, bỏ qua tệp metadata."""

    return sorted(
        path
        for path in MAPS_DIR.glob("level_*.json")
        if path.name != "level_metadata.json"
    )


@lru_cache(maxsize=None)
def load_level(name: str) -> tuple[Level, bool]:
    """Nạp và kiểm tra một màn chơi, có cache để tránh lặp lại.

    ``LevelLoader`` thực hiện kiểm tra tính hợp lệ và giải thử, nên kết quả
    ``solveable`` phản ánh đúng khả năng giải của màn.
    """

    return LevelLoader.load_level_from_file(MAPS_DIR / name)


def hidden_solution(level: Level) -> Assignment:
    """Lời giải ẩn đầy đủ của màn chơi."""

    return {
        index: level.get_person(index).get_is_criminal()
        for index in range(1, level.get_map_size() + 1)
    }


def build_initial_formula(level: Level) -> Formula:
    """KB công khai ban đầu: manh mối của các lá đang mở và trạng thái của chúng."""

    formula: Formula = []
    for index in level.get_initially_revealed_region():
        person = level.get_person(index)
        formula.append([index] if person.get_is_criminal() else [-index])
        formula.extend(person.get_clue().to_cnf())
    return formula


def build_full_formula(level: Level) -> Formula:
    """CNF đầy đủ của toàn bộ manh mối và các trạng thái ban đầu."""

    formula: Formula = []
    for index in range(1, level.get_map_size() + 1):
        formula.extend(level.get_person(index).get_clue().to_cnf())
    for index in level.get_initially_revealed_region():
        person = level.get_person(index)
        formula.append([index] if person.get_is_criminal() else [-index])
    return formula


def build_complete_knowledge_base(level: Level) -> Formula:
    """KB cuối cùng sau khi mọi người đã được mở: đủ manh mối và đủ đơn vị."""

    formula = build_full_formula(level)
    initially_revealed = level.get_initially_revealed_region()
    for index in range(1, level.get_map_size() + 1):
        if index in initially_revealed:
            continue
        person = level.get_person(index)
        formula.append([index] if person.get_is_criminal() else [-index])
    return formula


def is_cnf_satisfied(formula: Formula, assignment: Assignment) -> bool:
    """Kiểm tra một phép gán đầy đủ có thỏa mãn toàn bộ CNF hay không."""

    return all(
        any(
            assignment.get(abs(literal), False) == (literal > 0)
            for literal in clause
        )
        for clause in formula
    )


def is_sat(formula: Formula, map_size: int) -> bool:
    """Gọi DPLL để biết công thức có thỏa mãn được hay không."""

    return DpllSatSolver(map_size).SAT_solve(formula).is_SAT


def clause_counter(formula: Formula) -> Counter[tuple[int, ...]]:
    """Đếm mệnh đề không quan tâm thứ tự, phục vụ so sánh KB."""

    return Counter(tuple(clause) for clause in formula)


def max_variable(formula: Formula) -> int:
    """Chỉ số biến lớn nhất xuất hiện trong công thức."""

    return max(
        (abs(literal) for clause in formula for literal in clause),
        default=0,
    )


def all_assignments(indices: Iterable[int]) -> Iterator[Assignment]:
    """Sinh toàn bộ phép gán cho một tập chỉ số hữu hạn."""

    index_list = list(indices)
    for values in product([False, True], repeat=len(index_list)):
        yield dict(zip(index_list, values))


def cnf_is_satisfiable_with_primary_assignment(
    formula: Formula,
    primary_assignment: Assignment,
) -> bool:
    """Có tồn tại phép gán biến phụ để CNF đúng với phép gán chính hay không.

    Hàm này duyệt toàn bộ biến phụ. Nó chỉ dùng cho các vùng nhỏ trong kiểm
    thử, không dùng trong thuật toán chính.
    """

    num_variables = max(
        max_variable(formula),
        max(primary_assignment, default=0),
    )

    for values in product([False, True], repeat=num_variables):
        full_assignment = {
            index + 1: values[index] for index in range(num_variables)
        }
        if any(
            full_assignment[index] != value
            for index, value in primary_assignment.items()
        ):
            continue
        if is_cnf_satisfied(formula, full_assignment):
            return True

    return False


def brute_force_models(
    formula: Formula,
    num_variables: int,
) -> Iterator[Assignment]:
    """Sinh toàn bộ mô hình của một CNF nhỏ bằng vét cạn."""

    for values in product([False, True], repeat=num_variables):
        assignment = {
            index + 1: values[index] for index in range(num_variables)
        }
        if is_cnf_satisfied(formula, assignment):
            yield assignment
