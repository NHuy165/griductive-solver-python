"""A single playable Griductive session.

The session is the bridge between the game engine, the logic agent and the
web interface. It deliberately exposes only public information in ``state()``:
a face-down card never sends its status or clue to the browser.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from src.game.clue.clue import Clue
from src.game.core.core_types.exceptions import ExceptionBrokenClues
from src.game.core.core_types.level_solve_result import LevelSolveStatus
from src.game.core.core_types.miscellaneous import Assignment, Formula
from src.game.core.core_types.SAT_solve_result import SATSolveEvent
from src.game.core.core_types.verdict_result import VerdictResult
from src.game.core.level_loader import LevelLoader
from src.game.logic.game_engine import GameEngine
from src.game.logic.logic_agent import LogicAgent
from src.game.metrics.SAT_solves import count_SAT_solves_from_assignment_result
from src.game.metrics.events import count_events_from_assignment_result
from src.web.clue_text import describe_clue_vi

OCCUPATION_ICONS: dict[str, str] = {
    "Artist": "mdi--palette.svg",
    "Baker": "mdi--bread-slice.svg",
    "Banker": "mdi--bank.svg",
    "Chef": "mdi--chef-hat.svg",
    "Clerk": "mdi--briefcase.svg",
    "Cook": "mdi--pot-steam.svg",
    "Doctor": "mdi--stethoscope.svg",
    "Farmer": "mdi--sprout.svg",
    "Judge": "mdi--gavel.svg",
    "Mason": "mdi--hammer.svg",
    "Nurse": "mdi--medical-bag.svg",
    "Painter": "mdi--brush.svg",
    "Pilot": "mdi--airplane.svg",
    "Plumber": "mdi--pipe-wrench.svg",
    "Sailor": "mdi--sail-boat.svg",
    "Singer": "mdi--microphone.svg",
    "Tailor": "mdi--tape-measure.svg",
    "Teacher": "mdi--school.svg",
}

CLUE_ICONS: dict[str, str] = {
    "FACT": "mdi--account-check.svg",
    "SAME": "mdi--equal.svg",
    "DIFFERENT": "mdi--not-equal-variant.svg",
    "EXACTLY": "mdi--counter.svg",
    "AT_LEAST": "mdi--chevron-double-up.svg",
    "AT_MOST": "mdi--chevron-double-down.svg",
    "IMPLIES": "mdi--arrow-right-bold.svg",
    "COMPARE": "mdi--scale-balance.svg",
    "PARITY": "mdi--swap-horizontal.svg",
}


class GameSession:
    def __init__(self, level_path: Path, meta: dict[str, Any]) -> None:
        self.level_path = level_path
        self.meta = meta

        self.level, self.solveable = LevelLoader.load_level_from_file(level_path)
        self.engine = GameEngine(self.level)
        self.agent = LogicAgent(self.engine)
        self.map_size = self.level.get_map_size()

        self.formula: Formula = []
        self.flipped: set[int] = set()
        self.assignment: Assignment = {}
        self.trace: list[dict[str, Any]] = []
        self.step_count = 0
        self.last_auto: dict[str, Any] | None = None

        self._initial_flipped: set[int] = set()
        self._initial_assignment: Assignment = {}
        self.full_clauses = self._count_full_clauses()
        self.initial_clauses = 0
        self.reset()

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self.formula = self.engine.get_initial_formula()
        self.flipped = set(self.engine.get_initially_revealed_region())
        self.assignment = self.engine.get_initially_revealed_assignments()
        self._initial_flipped = set(self.flipped)
        self._initial_assignment = dict(self.assignment)
        self.initial_clauses = len(self.formula)
        self.trace = []
        self.step_count = 0
        self.last_auto = None

    def state(self) -> dict[str, Any]:
        people = [
            self._person_payload(index)
            for index in range(1, self.map_size + 1)
        ]
        revealed_clues = [
            self._clue_payload(index) for index in sorted(self.flipped)
        ]

        return {
            "level": {**self.meta, "solveable": self.solveable},
            "map_size": self.map_size,
            "people": people,
            "flipped": sorted(self.flipped),
            "initial_flipped": sorted(self._initial_flipped),
            "remaining": self.map_size - len(self.flipped),
            "solved": len(self.flipped) == self.map_size,
            "kb_clauses": len(self.formula),
            "revealed_clues": revealed_clues,
            "stats": {
                "primary": self.map_size,
                "auxiliary": self.engine.get_auxiliary_count(),
                "full_clauses": self.full_clauses,
                "initial_clauses": self.initial_clauses,
                "kb_clauses": len(self.formula),
                "initial_revealed": len(self._initial_flipped),
            },
            "trace": list(self.trace[-40:]),
            "last_auto": self.last_auto,
        }

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------

    def submit_verdict(self, index: int, verdict: str) -> dict[str, Any]:
        if not 1 <= index <= self.map_size:
            return self._error("Chỉ số nhân vật không hợp lệ.")

        if index in self.flipped:
            return self._error("Lá bài này đã được lật rồi.")

        is_criminal = verdict == "CRIMINAL"
        active_clue_ids = self._active_clue_ids()
        query = self._query(index, verdict)

        try:
            result, clue = self.engine.validate_verdict_and_provide_clue_if_correct(
                self.formula,
                index,
                is_criminal_prediction=is_criminal,
            )
        except ExceptionBrokenClues:
            return self._error(
                "Cơ sở tri thức hiện tại đã mâu thuẫn. Không thể tiếp tục màn chơi."
            )

        if result == VerdictResult.NOT_PROVABLE:
            return {
                "result": result.value,
                "message": (
                    "Chưa thể kết luận: cả hai khả năng tội phạm và vô tội "
                    "vẫn còn phù hợp với các manh mối đang mở."
                ),
                "state": self.state(),
                "revealed_index": None,
            }

        if result == VerdictResult.CONTRADICTED:
            return {
                "result": result.value,
                "message": (
                    "Sai hướng: trạng thái ngược lại mới là điều được suy ra "
                    "chắc chắn. Lá bài vẫn được giữ úp."
                ),
                "state": self.state(),
                "revealed_index": None,
            }

        assert result == VerdictResult.CORRECT
        assert clue is not None

        self.flipped.add(index)
        self.assignment[index] = is_criminal
        self.formula.append([index] if is_criminal else [-index])
        self.formula.extend(clue.to_cnf())
        self.step_count += 1
        self.trace.append(
            {
                "step": self.step_count,
                "kind": "manual",
                "active_clue_ids": active_clue_ids,
                "query": query,
                "verdict": verdict,
                "index": index,
                "coord": self._coord(index),
                "name": self.level.get_person(index).get_name(),
                "new_clue_id": f"CL-{index}",
            }
        )

        return {
            "result": result.value,
            "message": self._correct_message(index, is_criminal),
            "state": self.state(),
            "revealed_index": index,
        }

    def hint(self) -> dict[str, Any]:
        assignment_result = self.agent.assign_from_formula(self.formula)
        candidates = sorted(
            set(assignment_result.confirmed_assignments) - self.flipped
        )

        if not candidates:
            return {
                "hint": None,
                "message": (
                    "Hiện tại không còn nhân vật nào được suy ra chắc chắn "
                    "từ các manh mối đang mở."
                ),
                "state": self.state(),
            }

        index = candidates[0]
        person = self.level.get_person(index)
        related = self._clues_referencing(index)

        return {
            "hint": {
                "index": index,
                "coord": self._coord(index),
                "name": person.get_name(),
                "occupation": person.get_occupation(),
                "icon": self._occupation_icon(person.get_occupation()),
                "clue_ids": related,
            },
            "message": (
                f"Gợi ý: {person.get_name()} ({self._coord(index)}) đã có thể "
                "được kết luận. Hãy xem các manh mối được tô sáng."
            ),
            "state": self.state(),
        }

    def auto_solve(self) -> dict[str, Any]:
        start = perf_counter()
        try:
            result = self.agent.solve_from_state(
                self.formula, self.flipped, self.assignment
            )
        except ExceptionBrokenClues:
            return self._error(
                "Cơ sở tri thức hiện tại đã mâu thuẫn. Không thể tự động giải."
            )
        elapsed = perf_counter() - start

        steps: list[dict[str, Any]] = []
        event_totals = {
            SATSolveEvent.PROPAGATION: 0,
            SATSolveEvent.DECISION: 0,
            SATSolveEvent.BACKTRACK: 0,
        }
        sat_call_total = 0

        for wave_number, step in enumerate(result.solve_steps, start=1):
            new_assignments = step.assignment_result.confirmed_assignments
            owners = list(new_assignments.keys())
            active_clue_ids = [
                f"CL-{index}" for index in sorted(step.current_indices_flipped)
            ]
            new_people: list[dict[str, Any]] = []
            verdicts: list[dict[str, Any]] = []
            new_clue_ids: list[str] = []

            for owner, clue in zip(owners, step.revealed_clues):
                is_criminal = new_assignments[owner]
                status = "CRIMINAL" if is_criminal else "INNOCENT"
                person_payload = self._person_payload(
                    owner, status=status, clue=clue
                )
                new_people.append(person_payload)
                new_clue_ids.append(f"CL-{owner}")
                verdicts.append(
                    {
                        "index": owner,
                        "coord": self._coord(owner),
                        "name": self.level.get_person(owner).get_name(),
                        "status": status,
                        "clue_id": f"CL-{owner}",
                    }
                )

                self.flipped.add(owner)
                self.assignment[owner] = is_criminal
                self.formula.append([owner] if is_criminal else [-owner])
                self.step_count += 1
                self.trace.append(
                    {
                        "step": self.step_count,
                        "kind": "auto",
                        "wave": wave_number,
                        "active_clue_ids": active_clue_ids,
                        "query": self._query(owner, status),
                        "verdict": status,
                        "index": owner,
                        "coord": self._coord(owner),
                        "name": self.level.get_person(owner).get_name(),
                        "new_clue_id": f"CL-{owner}",
                    }
                )

            for clue in step.revealed_clues:
                self.formula.extend(clue.to_cnf())

            event_counts = count_events_from_assignment_result(
                step.assignment_result
            )
            for event, count in event_counts.items():
                event_totals[event] += count
            sat_calls = count_SAT_solves_from_assignment_result(
                step.assignment_result
            )
            sat_call_total += sat_calls

            steps.append(
                {
                    "wave": wave_number,
                    "active_clue_ids": active_clue_ids,
                    "verdicts": verdicts,
                    "new_people": new_people,
                    "new_clue_ids": new_clue_ids,
                    "sat_calls": sat_calls,
                    "events": {
                        event.value: count
                        for event, count in event_counts.items()
                    },
                    "kb_clauses_after": len(self.formula),
                }
            )

        summary = {
            "status": result.status.value,
            "waves": len(steps),
            "sat_calls": sat_call_total,
            "decisions": event_totals[SATSolveEvent.DECISION],
            "propagations": event_totals[SATSolveEvent.PROPAGATION],
            "backtracks": event_totals[SATSolveEvent.BACKTRACK],
            "time_ms": round(elapsed * 1000, 3),
            "final_flipped": len(self.flipped),
        }
        self.last_auto = summary

        message = self._auto_message(result.status, summary)
        return {
            "steps": steps,
            "summary": summary,
            "message": message,
            "state": self.state(),
        }

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _person_payload(
        self,
        index: int,
        status: str | None = None,
        clue: Clue | None = None,
    ) -> dict[str, Any]:
        person = self.level.get_person(index)
        revealed = status is not None or index in self.flipped

        payload: dict[str, Any] = {
            "index": index,
            "coord": self._coord(index),
            "name": person.get_name(),
            "occupation": person.get_occupation(),
            "icon": self._occupation_icon(person.get_occupation()),
            "revealed": revealed,
        }

        if revealed:
            if status is None:
                status = (
                    "CRIMINAL" if self.assignment[index] else "INNOCENT"
                )
            payload["status"] = status
            payload["clue"] = self._clue_payload(index, clue)

        return payload

    def _clue_payload(
        self, index: int, clue: Clue | None = None
    ) -> dict[str, Any]:
        person = self.level.get_person(index)
        resolved_clue = clue if clue is not None else person.get_clue()

        return {
            "id": f"CL-{index}",
            "owner": index,
            "owner_name": person.get_name(),
            "owner_coord": self._coord(index),
            "type": resolved_clue.get_type().value,
            "icon": CLUE_ICONS.get(
                resolved_clue.get_type().value, "mdi--help-circle.svg"
            ),
            "text": describe_clue_vi(self.level, resolved_clue),
            "region": sorted(set(resolved_clue.get_region())),
        }

    def _active_clue_ids(self) -> list[str]:
        return [f"CL-{index}" for index in sorted(self.flipped)]

    def _clues_referencing(self, index: int) -> list[str]:
        related: list[str] = []
        for owner in sorted(self.flipped):
            clue = self.level.get_person(owner).get_clue()
            if index in set(clue.get_region()):
                related.append(f"CL-{owner}")
        return related

    def _count_full_clauses(self) -> int:
        formula: Formula = []
        for index in range(1, self.map_size + 1):
            formula.extend(self.level.get_person(index).get_clue().to_cnf())
        for index in self.engine.get_initially_revealed_region():
            formula.append(
                [index]
                if self.level.get_person(index).get_is_criminal()
                else [-index]
            )
        return len(formula)

    def _occupation_icon(self, occupation: str) -> str:
        return OCCUPATION_ICONS.get(occupation, "mdi--account.svg")

    def _coord(self, index: int) -> str:
        row = (index - 1) // self.level_size() + 1
        column = chr(ord("A") + (index - 1) % self.level_size())
        return f"{column}{row}"

    def level_size(self) -> int:
        return int(self.map_size**0.5)

    def _query(self, index: int, verdict: str) -> str:
        assumed = f"C_{index}" if verdict == "INNOCENT" else f"¬C_{index}"
        return f"KB ∧ {assumed} → UNSAT"

    def _correct_message(self, index: int, is_criminal: bool) -> str:
        person = self.level.get_person(index)
        status = "TỘI PHẠM" if is_criminal else "VÔ TỘI"
        return (
            f"Chính xác! {person.get_name()} ({self._coord(index)}) là "
            f"{status}. Manh mối CL-{index} đã được mở."
        )

    def _auto_message(
        self, status: LevelSolveStatus, summary: dict[str, Any]
    ) -> str:
        if status == LevelSolveStatus.SUCCESS:
            return (
                f"Đã giải xong trong {summary['waves']} đợt lật, "
                f"{summary['sat_calls']} lần gọi SAT và "
                f"{summary['time_ms']:.2f} ms."
            )
        if status == LevelSolveStatus.STUCK:
            return (
                "Agent không còn kết luận nào có thể suy ra từ kiến thức "
                "công khai hiện tại."
            )
        return "Cơ sở tri thức đã mâu thuẫn trong quá trình suy luận."

    def _error(self, message: str) -> dict[str, Any]:
        return {
            "result": "ERROR",
            "message": message,
            "state": self.state(),
            "revealed_index": None,
        }
