"""Fixture dùng chung cho bộ kiểm thử."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers import MAPS_DIR, level_paths, load_level  # noqa: E402

from src.game.logic.game_engine import GameEngine  # noqa: E402
from src.game.logic.logic_agent import LogicAgent  # noqa: E402


@pytest.fixture(scope="session")
def maps_dir() -> Path:
    return MAPS_DIR


@pytest.fixture(scope="session")
def all_level_paths() -> list[Path]:
    return level_paths()


@pytest.fixture(scope="session")
def level_01():
    level, solveable = load_level("level_01.json")
    assert solveable
    return level


@pytest.fixture
def engine(level_01: object) -> GameEngine:
    return GameEngine(level_01)


@pytest.fixture
def agent(engine: GameEngine) -> LogicAgent:
    return LogicAgent(engine)
