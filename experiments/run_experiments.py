"""Chạy thí nghiệm cho toàn bộ 30 màn chơi và xuất dữ liệu mục 4.5.

Script này chỉ đọc và gọi API công khai của hệ thống. Mỗi lượt chạy được đặt
trong một tiến trình con để có thể áp đặt thời gian chờ cứng. Kết quả gồm:

- ``runs.csv``: một dòng cho mỗi lượt chạy.
- ``summary.csv``: tổng hợp theo từng màn.
- ``environment.json``: thông tin môi trường và cấu hình thí nghiệm.

Cách dùng::

    python -m experiments.run_experiments
    python -m experiments.run_experiments --repetitions 3 --timeout 60
    python -m experiments.run_experiments --analyze-only
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.game.core.core_types.SAT_solve_result import SATSolveEvent  # noqa: E402
from src.game.core.level import Level  # noqa: E402
from src.game.core.level_loader import LevelLoader  # noqa: E402
from src.game.logic.DPLL_SAT_solver import DpllSatSolver  # noqa: E402
from src.game.logic.game_engine import GameEngine  # noqa: E402
from src.game.logic.logic_agent import LogicAgent  # noqa: E402
from src.game.metrics.SAT_solves import (  # noqa: E402
    count_SAT_solves_from_level_solve,
)
from src.game.metrics.cnf_clauses import (  # noqa: E402
    count_cnf_clauses_generated_at_step,
)
from src.game.metrics.events import count_events_from_assignment_result  # noqa: E402
from src.game.metrics.level_solve_steps import (  # noqa: E402
    count_reveal_waves_from_level_solve,
)

MAPS_DIR = ROOT / "src" / "maps"
DEFAULT_OUTPUT_DIR = ROOT / "experiments" / "results"
DEFAULT_REPETITIONS = 3
DEFAULT_TIMEOUT_SECONDS = 60.0

RUN_FIELDS = [
    "run_id",
    "level_id",
    "level_number",
    "size",
    "repetition",
    "status",
    "solve_status",
    "solveable",
    "unique_check_passed",
    "solution_matches",
    "all_verdicts_entailed",
    "primary_variables",
    "auxiliary_variables",
    "total_variables",
    "initial_revealed",
    "deduction_steps",
    "new_verdicts",
    "initial_clauses",
    "full_clauses",
    "final_kb_clauses",
    "clue_clauses_generated",
    "sat_calls",
    "sat_calls_deduction",
    "sat_calls_uniqueness",
    "sat_calls_estimated",
    "decisions",
    "propagations",
    "backtracks",
    "load_time_ms",
    "uniqueness_check_ms",
    "runtime_ms",
    "total_time_ms",
    "timeout_s",
    "failure_reason",
    "error_type",
    "error_message",
]

SUMMARY_FIELDS = [
    "level_id",
    "level_number",
    "size",
    "runs",
    "success_count",
    "failed_count",
    "timeout_count",
    "error_count",
    "success_rate",
    "solveable",
    "unique_check_passed",
    "all_solutions_match",
    "all_verdicts_entailed",
    "primary_variables",
    "auxiliary_variables",
    "initial_revealed",
    "mean_deduction_steps",
    "mean_new_verdicts",
    "mean_initial_clauses",
    "mean_full_clauses",
    "mean_clue_clauses_generated",
    "mean_sat_calls",
    "mean_sat_calls_deduction",
    "mean_sat_calls_uniqueness",
    "mean_decisions",
    "mean_propagations",
    "mean_backtracks",
    "mean_load_time_ms",
    "mean_uniqueness_check_ms",
    "mean_runtime_ms",
    "stdev_runtime_ms",
    "min_runtime_ms",
    "median_runtime_ms",
    "max_runtime_ms",
    "mean_total_time_ms",
]

INT_FIELDS = {
    "level_number",
    "size",
    "repetition",
    "primary_variables",
    "auxiliary_variables",
    "total_variables",
    "initial_revealed",
    "deduction_steps",
    "new_verdicts",
    "initial_clauses",
    "full_clauses",
    "final_kb_clauses",
    "clue_clauses_generated",
    "sat_calls",
    "sat_calls_deduction",
    "sat_calls_uniqueness",
    "sat_calls_estimated",
    "decisions",
    "propagations",
    "backtracks",
    "runs",
    "success_count",
    "failed_count",
    "timeout_count",
    "error_count",
}

FLOAT_FIELDS = {
    "load_time_ms",
    "uniqueness_check_ms",
    "runtime_ms",
    "total_time_ms",
    "timeout_s",
    "success_rate",
    "mean_deduction_steps",
    "mean_new_verdicts",
    "mean_initial_clauses",
    "mean_full_clauses",
    "mean_clue_clauses_generated",
    "mean_sat_calls",
    "mean_sat_calls_deduction",
    "mean_sat_calls_uniqueness",
    "mean_decisions",
    "mean_propagations",
    "mean_backtracks",
    "mean_load_time_ms",
    "mean_uniqueness_check_ms",
    "mean_runtime_ms",
    "stdev_runtime_ms",
    "min_runtime_ms",
    "median_runtime_ms",
    "max_runtime_ms",
    "mean_total_time_ms",
}

BOOL_FIELDS = {
    "solveable",
    "unique_check_passed",
    "solution_matches",
    "all_verdicts_entailed",
}

_SAT_COUNTER = {"enabled": False, "calls": 0}


# ---------------------------------------------------------------------------
# Đo đạc và thực thi một lượt chạy
# ---------------------------------------------------------------------------


def _install_sat_counter() -> Callable[[Any, list[list[int]]], Any]:
    """Bọc ``DpllSatSolver.SAT_solve`` để đếm số lần gọi SAT thực tế."""

    original = DpllSatSolver.SAT_solve

    def counting_sat_solve(
        self: DpllSatSolver, formula: list[list[int]]
    ):
        if _SAT_COUNTER["enabled"]:
            _SAT_COUNTER["calls"] += 1
        return original(self, formula)

    DpllSatSolver.SAT_solve = counting_sat_solve
    return original


def _timed_call(
    function: Callable[[], Any],
) -> tuple[Any, float, int, Exception | None]:
    """Chạy một pha, trả về (kết quả, ms, số lần gọi SAT, lỗi nếu có)."""

    _SAT_COUNTER["enabled"] = True
    _SAT_COUNTER["calls"] = 0
    start = time.perf_counter()

    value: Any = None
    error: Exception | None = None
    try:
        value = function()
    except Exception as exc:  # noqa: BLE001 - cần giữ lại mọi lỗi để ghi CSV
        error = exc

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    calls = int(_SAT_COUNTER["calls"])
    _SAT_COUNTER["enabled"] = False

    return value, elapsed_ms, calls, error


def _level_number(path: Path) -> int:
    try:
        return int(path.stem.split("_")[1])
    except (IndexError, ValueError):
        return 0


def _read_level_size(path: Path) -> int | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        size = data.get("size")
        return int(size) if size is not None else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _base_row(path: Path, repetition: int, timeout_s: float) -> dict[str, Any]:
    number = _level_number(path)
    return {
        "run_id": f"L{number:02d}-R{repetition}",
        "level_id": path.name,
        "level_number": number,
        "size": _read_level_size(path),
        "repetition": repetition,
        "status": "",
        "solve_status": "",
        "solveable": None,
        "unique_check_passed": None,
        "solution_matches": None,
        "all_verdicts_entailed": None,
        "primary_variables": None,
        "auxiliary_variables": None,
        "total_variables": None,
        "initial_revealed": None,
        "deduction_steps": None,
        "new_verdicts": None,
        "initial_clauses": None,
        "full_clauses": None,
        "final_kb_clauses": None,
        "clue_clauses_generated": None,
        "sat_calls": None,
        "sat_calls_deduction": None,
        "sat_calls_uniqueness": None,
        "sat_calls_estimated": None,
        "decisions": None,
        "propagations": None,
        "backtracks": None,
        "load_time_ms": None,
        "uniqueness_check_ms": None,
        "runtime_ms": None,
        "total_time_ms": None,
        "timeout_s": timeout_s,
        "failure_reason": "",
        "error_type": "",
        "error_message": "",
    }


def _build_full_formula(level: Level) -> list[list[int]]:
    """CNF đầy đủ: toàn bộ manh mối và trạng thái của những người mở đầu."""

    formula: list[list[int]] = []
    for index in range(1, level.get_map_size() + 1):
        formula.extend(level.get_person(index).get_clue().to_cnf())

    for index in level.get_initially_revealed_region():
        person = level.get_person(index)
        formula.append([index] if person.get_is_criminal() else [-index])

    return formula


def _hidden_solution(level: Level) -> dict[int, bool]:
    return {
        index: level.get_person(index).get_is_criminal()
        for index in range(1, level.get_map_size() + 1)
    }


def _verify_entailment(level: Level, result: Any) -> bool:
    """Mọi phán quyết phải có KB ∧ phủ định là UNSAT."""

    max_variable = level.get_map_size()
    for step in result.solve_steps:
        for clause in step.current_formula:
            for literal in clause:
                max_variable = max(max_variable, abs(literal))

    for step in result.solve_steps:
        for index, is_criminal in step.assignment_result.confirmed_assignments.items():
            opposite = -index if is_criminal else index
            solver = DpllSatSolver(max_variable)
            if solver.SAT_solve(step.current_formula + [[opposite]]).is_SAT:
                return False

    return True


def _execute_run_inner(
    path: Path, repetition: int, timeout_s: float
) -> dict[str, Any]:
    row = _base_row(path, repetition, timeout_s)

    load_value, load_ms, _, load_error = _timed_call(
        lambda: LevelLoader.load_level_from_file(path)
    )
    row["load_time_ms"] = load_ms

    if load_error is not None:
        row.update(
            status="ERROR",
            failure_reason="load_error",
            error_type=type(load_error).__name__,
            error_message=str(load_error),
            total_time_ms=load_ms,
        )
        return row

    level, solveable = load_value
    row["solveable"] = bool(solveable)
    row["primary_variables"] = level.get_map_size()
    row["auxiliary_variables"] = level.get_auxiliary_count()
    row["total_variables"] = (
        row["primary_variables"] + row["auxiliary_variables"]
    )
    row["initial_revealed"] = len(level.get_initially_revealed_region())

    engine = GameEngine(level)
    agent = LogicAgent(engine)
    initial_formula = engine.get_initial_formula()
    full_formula = _build_full_formula(level)
    row["initial_clauses"] = len(initial_formula)
    row["full_clauses"] = len(full_formula)

    unique_value, unique_ms, unique_calls, unique_error = _timed_call(
        lambda: agent.unique_check(full_formula)
    )
    row["uniqueness_check_ms"] = unique_ms
    row["sat_calls_uniqueness"] = unique_calls

    if unique_error is not None:
        row.update(
            status="ERROR",
            failure_reason="uniqueness_check_error",
            error_type=type(unique_error).__name__,
            error_message=str(unique_error),
            total_time_ms=load_ms + unique_ms,
        )
        return row

    unique_ok = bool(unique_value)
    row["unique_check_passed"] = unique_ok

    result, solve_ms, deduction_calls, solve_error = _timed_call(
        agent.solve_level
    )
    row["runtime_ms"] = solve_ms
    row["sat_calls_deduction"] = deduction_calls
    row["sat_calls"] = deduction_calls + unique_calls

    if solve_error is not None:
        row.update(
            status="ERROR",
            failure_reason="solve_error",
            error_type=type(solve_error).__name__,
            error_message=str(solve_error),
            total_time_ms=load_ms + unique_ms + solve_ms,
        )
        return row

    hidden = _hidden_solution(level)
    solve_status = result.status.value
    solution_matches = result.final_assignment == hidden

    verification_error: Exception | None = None
    try:
        all_entailed = _verify_entailment(level, result)
    except Exception as exc:  # noqa: BLE001
        all_entailed = False
        verification_error = exc

    row["solve_status"] = solve_status
    row["solution_matches"] = solution_matches
    row["all_verdicts_entailed"] = all_entailed
    row["deduction_steps"] = count_reveal_waves_from_level_solve(result)
    row["new_verdicts"] = sum(
        len(step.assignment_result.confirmed_assignments)
        for step in result.solve_steps
    )
    row["clue_clauses_generated"] = sum(
        count_cnf_clauses_generated_at_step(step)
        for step in result.solve_steps
    )
    row["final_kb_clauses"] = row["initial_clauses"] + sum(
        len(step.revealed_clues)
        + sum(len(clue.to_cnf()) for clue in step.revealed_clues)
        for step in result.solve_steps
    )
    row["sat_calls_estimated"] = count_SAT_solves_from_level_solve(result)

    event_counts: Counter[SATSolveEvent] = Counter()
    for step in result.solve_steps:
        event_counts.update(
            count_events_from_assignment_result(step.assignment_result)
        )
    row["decisions"] = event_counts[SATSolveEvent.DECISION]
    row["propagations"] = event_counts[SATSolveEvent.PROPAGATION]
    row["backtracks"] = event_counts[SATSolveEvent.BACKTRACK]
    row["total_time_ms"] = load_ms + unique_ms + solve_ms

    reasons: list[str] = []
    if not solveable:
        reasons.append("level_not_solveable")
    if not unique_ok:
        reasons.append("unique_check_failed")
    if solve_status != "SUCCESS":
        reasons.append(f"solve_status_{solve_status.lower()}")
    if not solution_matches:
        reasons.append("solution_mismatch")
    if not all_entailed:
        reasons.append("verdict_not_entailed")

    if verification_error is not None:
        row.update(
            status="ERROR",
            failure_reason="verification_error",
            error_type=type(verification_error).__name__,
            error_message=str(verification_error),
        )
    elif reasons:
        row.update(status="FAILED", failure_reason=";".join(reasons))
    else:
        row.update(status="SUCCESS", failure_reason="")

    return row


def _execute_run(
    level_path: str, repetition: int, timeout_s: float
) -> dict[str, Any]:
    original_solve = _install_sat_counter()
    try:
        return _execute_run_inner(Path(level_path), repetition, timeout_s)
    finally:
        DpllSatSolver.SAT_solve = original_solve
        _SAT_COUNTER["enabled"] = False


def _child_entry(
    level_path: str,
    repetition: int,
    timeout_s: float,
    connection: Any,
) -> None:
    try:
        row = _execute_run(level_path, repetition, timeout_s)
    except Exception as exc:  # noqa: BLE001 - tiến trình con phải luôn gửi kết quả
        row = _base_row(Path(level_path), repetition, timeout_s)
        row.update(
            status="ERROR",
            failure_reason="child_process_error",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    try:
        connection.send(row)
    except Exception:  # noqa: BLE001 - không còn cách báo lỗi khác
        pass
    finally:
        connection.close()


def _timeout_row(path: Path, repetition: int, timeout_s: float) -> dict[str, Any]:
    row = _base_row(path, repetition, timeout_s)
    row.update(
        status="TIMEOUT",
        failure_reason="timeout",
        error_type="TimeoutError",
        error_message=f"Vượt quá {timeout_s:g} giây.",
        runtime_ms=timeout_s * 1000.0,
        total_time_ms=timeout_s * 1000.0,
    )
    return row


def _error_row(
    path: Path,
    repetition: int,
    timeout_s: float,
    error_type: str,
    error_message: str,
) -> dict[str, Any]:
    row = _base_row(path, repetition, timeout_s)
    row.update(
        status="ERROR",
        failure_reason="child_process_error",
        error_type=error_type,
        error_message=error_message,
    )
    return row


def _run_with_timeout(
    path: Path, repetition: int, timeout_s: float
) -> dict[str, Any]:
    context = mp.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_child_entry,
        args=(str(path), repetition, timeout_s, child_connection),
    )

    process.start()
    child_connection.close()

    start = time.monotonic()
    result: dict[str, Any] | None = None
    timed_out = False

    while True:
        if parent_connection.poll(0.05):
            try:
                result = parent_connection.recv()
            except EOFError:
                result = None
            break

        if not process.is_alive():
            if parent_connection.poll(0.5):
                try:
                    result = parent_connection.recv()
                except EOFError:
                    result = None
            break

        if time.monotonic() - start >= timeout_s:
            timed_out = True
            break

    if timed_out:
        process.terminate()
        process.join(timeout=5.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=5.0)
        result = _timeout_row(path, repetition, timeout_s)
    else:
        process.join(timeout=5.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=5.0)
        if result is None:
            result = _error_row(
                path,
                repetition,
                timeout_s,
                "ChildProcessError",
                f"Tiến trình con kết thúc mà không gửi kết quả (exitcode={process.exitcode}).",
            )

    parent_connection.close()
    return result


# ---------------------------------------------------------------------------
# CSV và tổng hợp
# ---------------------------------------------------------------------------


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        return f"{value:.6f}"
    return value


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _read_runs_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as file:
        for raw in csv.DictReader(file):
            row: dict[str, Any] = {}
            for key, value in raw.items():
                if value == "":
                    row[key] = None
                elif key in BOOL_FIELDS:
                    row[key] = value == "True"
                elif key in INT_FIELDS:
                    row[key] = int(value)
                elif key in FLOAT_FIELDS:
                    row[key] = float(value)
                else:
                    row[key] = value
            rows.append(row)
    return rows


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean_field(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [
        number
        for row in rows
        if (number := _as_float(row.get(field))) is not None
    ]
    return statistics.mean(values) if values else None


def _all_true(rows: list[dict[str, Any]], field: str) -> bool | None:
    values = [row.get(field) for row in rows if row.get(field) is not None]
    if not values:
        return None
    return all(value is True for value in values)


def build_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["level_id"])].append(row)

    summary: list[dict[str, Any]] = []
    for level_id in sorted(
        grouped,
        key=lambda key: int(grouped[key][0].get("level_number") or 0),
    ):
        group = grouped[level_id]
        successes = [row for row in group if row.get("status") == "SUCCESS"]
        status_counts = Counter(str(row.get("status")) for row in group)
        runtime_values = [
            number
            for row in successes
            if (number := _as_float(row.get("runtime_ms"))) is not None
        ]

        first = group[0]
        summary_row: dict[str, Any] = {
            "level_id": level_id,
            "level_number": first.get("level_number"),
            "size": first.get("size"),
            "runs": len(group),
            "success_count": status_counts.get("SUCCESS", 0),
            "failed_count": status_counts.get("FAILED", 0),
            "timeout_count": status_counts.get("TIMEOUT", 0),
            "error_count": status_counts.get("ERROR", 0),
            "success_rate": (
                status_counts.get("SUCCESS", 0) / len(group) if group else None
            ),
            "solveable": _all_true(group, "solveable"),
            "unique_check_passed": _all_true(group, "unique_check_passed"),
            "all_solutions_match": _all_true(group, "solution_matches"),
            "all_verdicts_entailed": _all_true(group, "all_verdicts_entailed"),
            "primary_variables": first.get("primary_variables"),
            "auxiliary_variables": first.get("auxiliary_variables"),
            "initial_revealed": first.get("initial_revealed"),
        }

        for field in (
            "deduction_steps",
            "new_verdicts",
            "initial_clauses",
            "full_clauses",
            "clue_clauses_generated",
            "sat_calls",
            "sat_calls_deduction",
            "sat_calls_uniqueness",
            "decisions",
            "propagations",
            "backtracks",
            "load_time_ms",
            "uniqueness_check_ms",
            "runtime_ms",
            "total_time_ms",
        ):
            summary_row[f"mean_{field}"] = _mean_field(successes, field)

        if runtime_values:
            summary_row["stdev_runtime_ms"] = (
                statistics.stdev(runtime_values)
                if len(runtime_values) >= 2
                else 0.0
            )
            summary_row["min_runtime_ms"] = min(runtime_values)
            summary_row["median_runtime_ms"] = statistics.median(runtime_values)
            summary_row["max_runtime_ms"] = max(runtime_values)
        else:
            summary_row["stdev_runtime_ms"] = None
            summary_row["min_runtime_ms"] = None
            summary_row["median_runtime_ms"] = None
            summary_row["max_runtime_ms"] = None

        summary.append(summary_row)

    return summary


# ---------------------------------------------------------------------------
# Môi trường
# ---------------------------------------------------------------------------


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    return completed.stdout.strip() if completed.returncode == 0 else None


def build_environment(
    repetitions: int, timeout_s: float, level_count: int
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "pytest_version": _package_version("pytest"),
        "flask_version": _package_version("flask"),
        "git_commit": _git_commit(),
        "repetitions": repetitions,
        "timeout_seconds": timeout_s,
        "level_count": level_count,
        "command": "python -m experiments.run_experiments",
        "metrics_notes": {
            "runtime_ms": "Chỉ đo LogicAgent.solve_level.",
            "load_time_ms": "Đo LevelLoader.load_level_from_file, gồm kiểm tra hợp lệ và giải thử.",
            "uniqueness_check_ms": "Đo LogicAgent.unique_check trên CNF đầy đủ.",
            "sat_calls": "Số lần gọi DpllSatSolver.SAT_solve thực tế trong giai đoạn giải và kiểm tra duy nhất.",
            "sat_calls_estimated": "Ước lượng theo count_SAT_solves_from_level_solve của hệ thống.",
            "events": "Quyết định, lan truyền và quay lui được tổng hợp từ sự kiện của mọi lần gọi SAT trong các bước suy diễn.",
        },
    }


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Có" if value else "Không"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _discover_level_paths() -> list[Path]:
    paths = [
        path
        for path in MAPS_DIR.glob("level_*.json")
        if path.name != "level_metadata.json"
    ]
    return sorted(paths, key=_level_number)


def _parse_levels(value: str | None) -> set[int] | None:
    if not value:
        return None

    numbers: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            numbers.update(range(int(start_text), int(end_text) + 1))
        else:
            numbers.add(int(part))
    return numbers


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(
        description="Chạy thí nghiệm Griductive và xuất dữ liệu CSV."
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
        help=f"Số lần lặp mỗi màn (mặc định {DEFAULT_REPETITIONS}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Timeout mỗi lượt, tính bằng giây (mặc định {DEFAULT_TIMEOUT_SECONDS:g}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Thư mục chứa runs.csv, summary.csv và environment.json.",
    )
    parser.add_argument(
        "--levels",
        type=str,
        default=None,
        help="Chỉ chạy một số màn, ví dụ '1,3,5-7'.",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Đọc lại runs.csv và tạo lại summary.csv, không chạy lại.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_path = output_dir / "runs.csv"
    summary_path = output_dir / "summary.csv"
    environment_path = output_dir / "environment.json"

    environment_written = False

    if args.analyze_only:
        if not runs_path.exists():
            parser.error(f"Không tìm thấy {runs_path} để phân tích.")
        rows = _read_runs_csv(runs_path)
        if environment_path.exists():
            environment = json.loads(
                environment_path.read_text(encoding="utf-8")
            )
        else:
            environment = build_environment(
                args.repetitions,
                args.timeout,
                len({row["level_id"] for row in rows}),
            )
        print(f"Đã đọc {len(rows)} lượt chạy từ {runs_path}.")
    else:
        paths = _discover_level_paths()
        selected_levels = _parse_levels(args.levels)
        if selected_levels is not None:
            paths = [
                path
                for path in paths
                if _level_number(path) in selected_levels
            ]
        if not paths:
            parser.error("Không tìm thấy màn chơi nào để chạy.")

        rows = []
        total = len(paths) * args.repetitions
        for path in paths:
            for repetition in range(1, args.repetitions + 1):
                row = _run_with_timeout(path, repetition, args.timeout)
                rows.append(row)
                print(
                    f"[{len(rows)}/{total}] {row['run_id']} "
                    f"{row['status']} runtime_ms={_fmt(row.get('runtime_ms'), 2)}"
                )

        _write_csv(runs_path, RUN_FIELDS, rows)
        environment = build_environment(
            args.repetitions, args.timeout, len(paths)
        )
        environment_path.write_text(
            json.dumps(environment, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        environment_written = True

    summary = build_summary(rows)
    _write_csv(summary_path, SUMMARY_FIELDS, summary)

    if not environment_path.exists():
        environment_path.write_text(
            json.dumps(environment, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        environment_written = True

    if not args.analyze_only:
        print(f"Đã ghi {runs_path}")
    print(f"Đã ghi {summary_path}")
    if environment_written:
        print(f"Đã ghi {environment_path}")
    else:
        print(f"Đã dùng {environment_path}")


if __name__ == "__main__":
    main()
