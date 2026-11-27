"""Kiểm thử các thành phần của trình chạy thí nghiệm.

Các kiểm thử không chạy toàn bộ 90 lượt; chúng kiểm tra một lượt thật trên
màn 01, việc ghi/đọc CSV, tổng hợp theo màn và việc script không tạo tệp
Markdown.
"""

from __future__ import annotations

import sys

import pytest

from experiments.run_experiments import (
    RUN_FIELDS,
    _execute_run,
    _parse_levels,
    _read_runs_csv,
    _run_with_timeout,
    _write_csv,
    build_summary,
    main,
)
from tests.helpers import MAPS_DIR


@pytest.fixture(scope="module")
def level_01_run() -> dict:
    return _execute_run(str(MAPS_DIR / "level_01.json"), 1, 60.0)


def test_execute_run_records_all_required_metrics(level_01_run: dict) -> None:
    row = level_01_run

    assert row["status"] == "SUCCESS"
    assert row["solve_status"] == "SUCCESS"
    assert row["solveable"] is True
    assert row["unique_check_passed"] is True
    assert row["solution_matches"] is True
    assert row["all_verdicts_entailed"] is True

    assert row["primary_variables"] == 9
    assert row["auxiliary_variables"] == 0
    assert row["total_variables"] == 9
    assert row["initial_revealed"] == 1
    assert row["deduction_steps"] == 7
    assert row["new_verdicts"] == 8

    assert row["initial_clauses"] == 3
    assert row["full_clauses"] == 19
    assert row["final_kb_clauses"] == 27
    assert row["clue_clauses_generated"] == 16

    assert row["sat_calls_uniqueness"] == 2
    assert row["sat_calls_deduction"] >= 1
    assert row["sat_calls"] == (
        row["sat_calls_deduction"] + row["sat_calls_uniqueness"]
    )
    assert row["sat_calls_estimated"] == row["sat_calls_deduction"]

    assert row["decisions"] >= 0
    assert row["propagations"] > 0
    assert row["backtracks"] >= 0
    assert row["load_time_ms"] >= 0.0
    assert row["uniqueness_check_ms"] >= 0.0
    assert row["runtime_ms"] >= 0.0
    assert row["total_time_ms"] == pytest.approx(
        row["load_time_ms"]
        + row["uniqueness_check_ms"]
        + row["runtime_ms"]
    )
    assert row["timeout_s"] == 60.0


def test_csv_round_trip_preserves_types(
    tmp_path, level_01_run: dict
) -> None:
    path = tmp_path / "runs.csv"

    _write_csv(path, RUN_FIELDS, [level_01_run])
    rows = _read_runs_csv(path)

    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "SUCCESS"
    assert row["solveable"] is True
    assert row["solution_matches"] is True
    assert row["level_number"] == 1
    assert row["size"] == 3
    assert row["deduction_steps"] == 7
    assert row["runtime_ms"] == pytest.approx(
        level_01_run["runtime_ms"], abs=1e-6
    )


def test_build_summary_aggregates_repetitions(level_01_run: dict) -> None:
    rows = [
        {
            **level_01_run,
            "run_id": f"L01-R{repetition}",
            "repetition": repetition,
        }
        for repetition in range(1, 4)
    ]

    summary = build_summary(rows)

    assert len(summary) == 1
    item = summary[0]
    assert item["level_id"] == "level_01.json"
    assert item["runs"] == 3
    assert item["success_count"] == 3
    assert item["failed_count"] == 0
    assert item["timeout_count"] == 0
    assert item["error_count"] == 0
    assert item["success_rate"] == 1.0
    assert item["all_solutions_match"] is True
    assert item["all_verdicts_entailed"] is True
    assert item["mean_runtime_ms"] == pytest.approx(
        level_01_run["runtime_ms"]
    )
    assert item["stdev_runtime_ms"] == pytest.approx(0.0)
    assert item["mean_sat_calls"] == pytest.approx(
        level_01_run["sat_calls"]
    )


def test_parse_levels_supports_ranges() -> None:
    assert _parse_levels(None) is None
    assert _parse_levels("1,3,5-7") == {1, 3, 5, 6, 7}
    assert _parse_levels(" 2 , 4 ") == {2, 4}


def test_load_error_is_recorded(tmp_path) -> None:
    row = _execute_run(str(tmp_path / "missing.json"), 1, 60.0)

    assert row["status"] == "ERROR"
    assert row["failure_reason"] == "load_error"
    assert row["error_type"] == "FileNotFoundError"
    assert row["load_time_ms"] >= 0.0
    assert row["runtime_ms"] is None


def test_timeout_is_recorded() -> None:
    row = _run_with_timeout(MAPS_DIR / "level_01.json", 1, 0.001)

    assert row["status"] == "TIMEOUT"
    assert row["failure_reason"] == "timeout"
    assert row["error_type"] == "TimeoutError"
    assert row["runtime_ms"] == pytest.approx(1.0)
    assert row["total_time_ms"] == pytest.approx(1.0)


def test_analyze_only_does_not_create_markdown(
    tmp_path,
    monkeypatch,
    capsys,
    level_01_run: dict,
) -> None:
    _write_csv(tmp_path / "runs.csv", RUN_FIELDS, [level_01_run])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_experiments",
            "--analyze-only",
            "--output-dir",
            str(tmp_path),
        ],
    )

    main()

    output = capsys.readouterr().out
    assert (tmp_path / "summary.csv").exists()
    assert not (tmp_path / "report.md").exists()
    assert "report.md" not in output
